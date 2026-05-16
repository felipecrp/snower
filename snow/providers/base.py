"""Abstract provider interface for fetching references and citations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from snow.domain.identity import WorkRef
from snow.domain.models import Work


class Provider(ABC):
    """Fetches backward references and forward citations for a given work."""

    @abstractmethod
    def fetch_references(self, work: Work) -> list[WorkRef]:
        """Return works that `work` cites (backward snowballing)."""
        ...

    @abstractmethod
    def fetch_citations(self, work: Work) -> list[WorkRef]:
        """Return works that cite `work` (forward snowballing)."""
        ...
