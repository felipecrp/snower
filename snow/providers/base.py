"""Abstract provider interface for fetching references and citations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from snow.domain.models import BibliographicWork
from snow.domain.models import Work


class Provider(ABC):
    """Fetches backward references and forward citations for a given work."""

    @abstractmethod
    def fetch_references(self, work: Work) -> list[BibliographicWork]:
        """Return works that `work` cites (backward snowballing)."""
        ...

    @abstractmethod
    def fetch_citations(self, work: Work) -> list[BibliographicWork]:
        """Return works that cite `work` (forward snowballing)."""
        ...

    def enrich_works(self, works: list[Work]) -> list[Work]:
        """Fill missing bibliographic metadata. Default: noop."""
        return list(works)
