"""OpenAlex provider using the public API.

Endpoint docs: https://docs.openalex.org/api-entities/works

No API key required. Using the polite pool (via email in User-Agent) gives
priority access and higher rate limits (~10 req/s).

Set an email in project.yml for polite pool access:

  providers:
    - name: openalex
      options:
        email: you@example.com

References are fetched in bulk (one request for up to 200 IDs).
Citations use a filter query (paginated if needed).
"""

from __future__ import annotations

import logging
import re

import httpx

from snow.domain.identity import BibliographicWork
from snow.domain.models import Work
from .base import Provider

logger = logging.getLogger(__name__)

_BASE = "https://api.openalex.org"
_TITLE_MATCH_THRESHOLD = 0.4  # minimum Jaccard score to accept a title match


def _titles_match(query: str, found: str) -> bool:
    """Return True if the two titles are close enough to be the same paper.

    Handles the case where OpenAlex truncates subtitles (e.g. stores only the
    part before the colon).  If the found title's words are a subset of the
    query title's words and the found title has at least 2 meaningful words,
    we treat it as a match.
    """
    def words(s: str) -> set[str]:
        return {w.lower() for w in re.findall(r"\w+", s) if len(w) > 2}
    q, f = words(query), words(found)
    if not q or not f:
        return False
    jaccard = len(q & f) / len(q | f)
    truncated_match = len(f) >= 2 and f.issubset(q)
    return jaccard >= _TITLE_MATCH_THRESHOLD or truncated_match


def _abstract_from_inverted_index(index: dict | None) -> str | None:
    if not index:
        return None
    positions: dict[int, str] = {}
    for word, indexes in index.items():
        for i in indexes or []:
            positions[i] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


_WORK_FIELDS = "title,authorships,publication_year,doi,primary_location,best_oa_location,abstract_inverted_index"
_PAGE_SIZE = 200
_MAX_CITATIONS = 1000


class OpenAlexProvider(Provider):
    """Fetches references and citations from the OpenAlex API."""

    def __init__(self, email: str | None = None) -> None:
        self._email = email
        agent = f"snow/1.0 (mailto:{email})" if email else "snow/1.0"
        self._client = httpx.Client(
            base_url=_BASE,
            headers={"User-Agent": agent},
            timeout=30,
        )

    def _params(self, extra: dict | None = None) -> dict:
        p: dict = {}
        if self._email:
            p["mailto"] = self._email
        if extra:
            p.update(extra)
        return p

    def _get(self, path: str, params: dict) -> dict | None:
        try:
            resp = self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("OpenAlex HTTP %s for %s", exc.response.status_code, path)
            return None
        except Exception as exc:
            logger.error("OpenAlex request failed for %s: %s", path, exc)
            return None

    def _work_id(self, work: Work) -> str | None:
        """Return the OpenAlex work ID (e.g. 'W2741809809')."""
        if work.doi:
            data = self._get(f"/works/doi:{work.doi}", self._params())
            if data and data.get("id"):
                return data["id"].rsplit("/", 1)[-1]
            logger.debug("OpenAlex: DOI lookup failed for %s; falling back to title search", work.doi)

        # Build candidate queries: full title + main title (before first colon/dash).
        main_title = re.split(r"[:—]", work.title, maxsplit=1)[0].strip()
        titles_to_try = [work.title] if main_title == work.title else [work.title, main_title]

        # Academic papers often appear in OpenAlex under the online-first year,
        # which may differ by ±1 from the proceedings/journal print year.
        years = [work.year] if work.year else [None]
        if work.year:
            years += [work.year - 1, work.year + 1]

        for raw_title in titles_to_try:
            clean = re.sub(r"[^\w\s]", " ", raw_title)
            for year in years:
                year_filter = f"publication_year:{year}" if year else None
                candidates = [
                    {"filter": f"title.search:{clean}" + (f",{year_filter}" if year_filter else ""), "per-page": 1},
                    {"search": clean, **({"filter": year_filter} if year_filter else {}), "per-page": 1},
                ]
                for extra in candidates:
                    extra["select"] = "id,title,publication_year"
                    data = self._get("/works", self._params(extra))
                    if not data:
                        continue
                    results = data.get("results") or []
                    if not results:
                        continue
                    found = results[0]
                    found_title = found.get("title") or ""
                    if not _titles_match(work.title, found_title):
                        logger.debug("OpenAlex: title mismatch '%s' → '%s'", work.title[:50], found_title[:50])
                        continue
                    oa_id = found["id"].rsplit("/", 1)[-1]
                    logger.debug("OpenAlex resolved '%s' → %s", work.title[:60], oa_id)
                    return oa_id

        logger.warning("OpenAlex: no reliable match for '%s'", work.title)
        return None

    def _work_data(self, work: Work) -> dict | None:
        work_id = self._work_id(work)
        if not work_id:
            return None
        return self._get(
            f"/works/{work_id}",
            self._params({"select": "id,title,doi,primary_location,best_oa_location,abstract_inverted_index"}),
        )

    def enrich_work(self, work: Work) -> Work:
        """Fill missing bibliographic fields from OpenAlex without overwriting originals."""
        if work.doi and work.venue and work.url and work.pdf_url and work.abstract:
            return work
        data = self._work_data(work)
        if not data:
            return work
        ref = self._to_work_ref(data)
        if not ref:
            return work
        return work.model_copy(update={
            "doi": work.doi or ref.doi,
            "venue": work.venue or ref.venue,
            "url": work.url or ref.url,
            "pdf_url": work.pdf_url or ref.pdf_url,
            "abstract": work.abstract or ref.abstract,
        })

    def enrich_works(self, works: list[Work]) -> list[Work]:
        return [self.enrich_work(work) for work in works]

    def _to_work_ref(self, item: dict) -> BibliographicWork | None:
        title = item.get("title")
        if not title:
            return None
        year = item.get("publication_year")
        authors = tuple(
            a["author"]["display_name"]
            for a in (item.get("authorships") or [])
            if a.get("author") and a["author"].get("display_name")
        )
        raw_doi = item.get("doi") or ""
        doi = raw_doi.removeprefix("https://doi.org/") or None
        primary_location = item.get("primary_location") or {}
        best_oa_location = item.get("best_oa_location") or {}
        source = primary_location.get("source") or {}
        venue = source.get("display_name") or None
        url = primary_location.get("landing_page_url") or raw_doi or None
        pdf_url = best_oa_location.get("pdf_url") or primary_location.get("pdf_url") or None
        abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
        return BibliographicWork(
            title=title,
            year=year,
            authors=authors,
            doi=doi,
            venue=venue,
            url=url,
            pdf_url=pdf_url,
            abstract=abstract,
        )

    def fetch_references(self, work: Work) -> list[BibliographicWork]:
        work_id = self._work_id(work)
        if not work_id:
            return []

        # The work object contains referenced_works as a list of OpenAlex IDs.
        data = self._get(f"/works/{work_id}", self._params({"select": "referenced_works"}))
        if not data:
            return []

        ref_ids = data.get("referenced_works") or []
        if not ref_ids:
            logger.warning("OpenAlex: 0 references for '%s'", work.title)
            return []

        # Batch-fetch referenced works in chunks of _PAGE_SIZE.
        refs: list[BibliographicWork] = []
        for i in range(0, len(ref_ids), _PAGE_SIZE):
            chunk = ref_ids[i : i + _PAGE_SIZE]
            ids_filter = "|".join(wid.rsplit("/", 1)[-1] for wid in chunk)
            batch = self._get(
                "/works",
                self._params({"filter": f"openalex_id:{ids_filter}", "per-page": _PAGE_SIZE, "select": _WORK_FIELDS}),
            )
            if not batch:
                continue
            for item in batch.get("results") or []:
                ref = self._to_work_ref(item)
                if ref:
                    refs.append(ref)

        return refs

    def fetch_citations(self, work: Work) -> list[BibliographicWork]:
        work_id = self._work_id(work)
        if not work_id:
            return []

        refs: list[BibliographicWork] = []
        page = 1
        while len(refs) < _MAX_CITATIONS:
            data = self._get(
                "/works",
                self._params({
                    "filter": f"cites:{work_id}",
                    "per-page": _PAGE_SIZE,
                    "page": page,
                    "select": _WORK_FIELDS,
                }),
            )
            if not data:
                break
            results = data.get("results") or []
            for item in results:
                ref = self._to_work_ref(item)
                if ref:
                    refs.append(ref)
            if len(results) < _PAGE_SIZE:
                break
            page += 1

        if not refs:
            logger.warning("OpenAlex: 0 citations for '%s'", work.title)
        return refs
