from enum import Enum

from pydantic import BaseModel


class CriterionType(str, Enum):
    """Whether a criterion signals inclusion or exclusion."""

    inclusion = "inclusion"
    exclusion = "exclusion"


class Criterion(BaseModel):
    """An inclusion or exclusion criterion used to screen papers."""

    id: str
    """Stable identifier for the criterion."""
    name: str
    """Human-readable label."""
    type: CriterionType
    """Whether this criterion marks a paper as included or excluded."""


class Phase(BaseModel):
    """A reading phase in the review protocol (e.g., title screening)."""

    id: str
    """Stable identifier for the phase."""
    name: str
    """Human-readable label."""


class Researcher(BaseModel):
    """A researcher participating in the review."""

    email: str
    """Unique identifier; also the key in assessment dicts and filenames."""
    name: str
    """Display name."""


class Assessment(BaseModel):
    """A researcher's screening opinion: criterion, phase, and optional comment."""

    criterion: Criterion
    """The criterion chosen for this assessment."""
    phase: Phase
    """The reading phase in which the assessment was made."""
    comment: str | None = None
    """Optional free-text note from the researcher."""

    @property
    def included(self) -> bool:
        """True when the criterion is an inclusion criterion, False for exclusion."""
        return self.criterion.type is CriterionType.inclusion
