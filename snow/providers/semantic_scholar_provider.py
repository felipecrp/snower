"""Semantic Scholar provider using the public Graph API.

Endpoint docs: https://api.semanticscholar.org/api-docs/graph

Rate limits:
  - Without API key: ~1 req/s
  - With API key:    100 req/s (free key at semanticscholar.org/product/api)

Set an API key in project.yml to avoid rate-limit errors on large reviews:

  providers:
    - name: semantic_scholar
      options:
        api_key: <your-key>

If a work has a DOI the paper is looked up directly (no search step needed).
For works without DOI, a title+first-author search is used as fallback.
"""

from __future__ import annotations

import logging
import time

import httpx

from snow.domain.models import BibliographicWork
from snow.domain.models import Work
from .base import Provider

logger = logging.getLogger(__name__)

_BASE = "https://api.semanticscholar.org/graph/v1"
_REF_FIELDS = "title,authors,year,externalIds"
_SEARCH_FIELDS = "paperId,title"
_LIMIT = 1000
_RATE_LIMIT_DELAY = 2.0  # seconds between requests without API key


class SemanticScholarProvider(Provider):
    """Fetches references and citations from the Semantic Scholar Graph API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        headers = {"x-api-key": api_key} if api_key else {}
        self._client = httpx.Client(
            base_url=_BASE,
            headers=headers,
            timeout=30,
        )

    def _throttle(self) -> None:
        if not self._api_key:
            time.sleep(_RATE_LIMIT_DELAY)

    def _get(self, path: str, params: dict, *, _retries: int = 3) -> dict | None:
        self._throttle()
        try:
            resp = self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                if _retries > 0:
                    wait = _RATE_LIMIT_DELAY * (4 - _retries) * 5  # 10s, 20s, 30s
                    logger.warning(
                        "Semantic Scholar rate limit — waiting %ds before retry (%d left)...",
                        wait, _retries - 1,
                    )
                    time.sleep(wait)
                    return self._get(path, params, _retries=_retries - 1)
                logger.error(
                    "Semantic Scholar rate limit persists after retries. "
                    "Get a free API key at semanticscholar.org/product/api and add it to "
                    "project.yml under providers[name=semantic_scholar].options.api_key"
                )
            else:
                logger.error("Semantic Scholar HTTP %s for %s", exc.response.status_code, path)
            return None
        except Exception as exc:
            logger.error("Semantic Scholar request failed for %s: %s", path, exc)
            return None

    def _paper_id(self, work: Work) -> str | None:
        """Return a Semantic Scholar paper identifier.

        Uses DOI directly when available; falls back to title search.
        """
        if work.doi:
            return f"DOI:{work.doi}"

        query = work.title
        if work.authors:
            query += " " + work.authors[0].split(",")[0].strip()

        data = self._get("/paper/search", {"query": query, "fields": _SEARCH_FIELDS, "limit": 1})
        if data is None:
            return None
        papers = data.get("data") or []
        if not papers:
            logger.warning("Semantic Scholar: no result for '%s'", work.title)
            return None
        return papers[0]["paperId"]

    def _to_work_ref(self, paper: dict) -> BibliographicWork | None:
        title = paper.get("title")
        if not title:
            return None
        year = paper.get("year")
        authors = tuple(a["name"] for a in paper.get("authors") or [])
        doi = (paper.get("externalIds") or {}).get("DOI")
        return BibliographicWork(title=title, year=year, authors=authors, doi=doi)

    def _fetch_related(self, work: Work, endpoint: str, paper_key: str) -> list[BibliographicWork]:
        paper_id = self._paper_id(work)
        if not paper_id:
            return []

        data = self._get(f"/paper/{paper_id}/{endpoint}", {"fields": _REF_FIELDS, "limit": _LIMIT})
        if data is None:
            return []

        refs: list[BibliographicWork] = []
        for item in data.get("data") or []:
            ref = self._to_work_ref(item.get(paper_key) or {})
            if ref:
                refs.append(ref)

        if not refs:
            logger.warning(
                "Semantic Scholar: 0 %s for '%s' (publisher may restrict access)",
                endpoint, work.title,
            )
        return refs

    def fetch_references(self, work: Work) -> list[BibliographicWork]:
        return self._fetch_related(work, "references", "citedPaper")

    def fetch_citations(self, work: Work) -> list[BibliographicWork]:
        return self._fetch_related(work, "citations", "citingPaper")
