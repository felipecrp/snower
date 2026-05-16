"""Google Scholar provider via the `scholarly` scraping library.

Note: Google Scholar has no official API. The `scholarly` library works by
scraping Scholar's web interface, which means:
- Rate limits apply (Scholar may return CAPTCHA after many requests).
- References are only available when Scholar shows them for the paper.
- Results may not be exhaustive.

For high-volume use, configure a proxy via scholarly.use_proxy().
"""

from __future__ import annotations

import logging
import time

from snow.domain.identity import WorkRef
from snow.domain.models import Work
from .base import Provider

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 2.0  # seconds between Scholar requests


def _to_work_ref(bib: dict) -> WorkRef | None:
    title = bib.get("title")
    if not title:
        return None
    year_raw = bib.get("pub_year") or bib.get("year")
    try:
        year = int(year_raw) if year_raw else None
    except (ValueError, TypeError):
        year = None
    raw_authors = bib.get("author", "")
    authors: tuple[str, ...] = tuple(a.strip() for a in raw_authors.split(" and ") if a.strip())
    return WorkRef(title=title, year=year, authors=authors)


class ScholarlyProvider(Provider):
    """Fetches references and citations from Google Scholar."""

    def _scholarly(self):
        try:
            from scholarly import scholarly  # type: ignore[import-untyped]
            return scholarly
        except ImportError:
            raise RuntimeError("Install 'scholarly' to use the Google Scholar provider.")

    def _find_pub(self, work: Work):
        s = self._scholarly()
        query = work.title
        if work.authors:
            # First author surname improves precision
            query += " " + work.authors[0].split(",")[0].strip()

        time.sleep(_REQUEST_DELAY)
        try:
            pub = next(s.search_pubs(query))
        except StopIteration:
            logger.warning("No Scholar result for: %s", work.title)
            return None
        except Exception as exc:
            logger.error("Scholar search failed for '%s': %s", work.title, exc)
            return None

        return pub

    def fetch_references(self, work: Work) -> list[WorkRef]:
        s = self._scholarly()
        pub = self._find_pub(work)
        if pub is None:
            return []

        time.sleep(_REQUEST_DELAY)
        try:
            filled = s.fill(pub, sections=["references"])
        except Exception as exc:
            logger.error("Could not fetch references for '%s': %s", work.title, exc)
            return []

        refs: list[WorkRef] = []
        for ref in filled.get("references", []):
            bib = ref.get("bib", {})
            work_ref = _to_work_ref(bib)
            if work_ref:
                refs.append(work_ref)
        return refs

    def fetch_citations(self, work: Work) -> list[WorkRef]:
        s = self._scholarly()
        pub = self._find_pub(work)
        if pub is None:
            return []

        refs: list[WorkRef] = []
        time.sleep(_REQUEST_DELAY)
        try:
            for citing in s.citedby(pub):
                bib = citing.get("bib", {})
                work_ref = _to_work_ref(bib)
                if work_ref:
                    refs.append(work_ref)
        except Exception as exc:
            logger.error("Could not fetch citations for '%s': %s", work.title, exc)
        return refs
