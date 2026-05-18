"""Domain models for snow.

These Pydantic models describe everything persisted in a project directory.
They are designed to round-trip cleanly to .bib + .yml files on disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import AliasChoices, BaseModel, Field, field_validator

from snow.domain.identity import WorkRef


class SetKind(StrEnum):
    START = "start"
    BACKWARD = "backward"
    FORWARD = "forward"
    ORPHAN = "orphan"


class CriterionKind(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


class Verdict(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


_ID_RE = re.compile(r"^[a-z0-9_]+$")


class Researcher(BaseModel):
    email: str
    name: str
    assignment_percentage: int = 100

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Researcher email is required")
        return v


class Criterion(BaseModel):
    id: str
    kind: CriterionKind
    description: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, v: str) -> str:
        normalized = v.lower().strip()
        if not _ID_RE.match(normalized):
            raise ValueError(f"Criterion id must contain only letters, digits, or underscores (got {v!r})")
        return normalized


class Phase(BaseModel):
    id: str
    description: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, v: str) -> str:
        normalized = v.lower().strip()
        if not _ID_RE.match(normalized):
            raise ValueError(f"Phase id must contain only letters, digits, or underscores (got {v!r})")
        return normalized


class ProviderConfig(BaseModel):
    name: str
    enabled: bool = True
    options: dict[str, str] = Field(default_factory=dict)


class Project(BaseModel):
    name: str
    description: str | None = None
    researchers: list[Researcher] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    phases: list[Phase] = Field(default_factory=list)
    providers: list[ProviderConfig] = Field(default_factory=list)


class Bidding(BaseModel):
    researcher_id: str
    work_ids: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class BibliographicWork:
    """Provider/import result: identity fields plus optional bibliographic metadata."""

    title: str | None = None
    year: int | None = None
    authors: tuple[str, ...] = ()
    doi: str | None = None
    venue: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    abstract: str | None = None

    def ref(self) -> WorkRef:
        return WorkRef(title=self.title, year=self.year, authors=self.authors)


class Work(BaseModel):
    """A bibliographic entry as it appears inside a set."""

    bib_key: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    abstract: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)
    last_backward_snowballed_at: datetime | None = None
    last_forward_snowballed_at: datetime | None = None
    last_backward_found: int | None = None
    last_forward_found: int | None = None
    has_local_pdf: bool = False


class Set(BaseModel):
    """One iteration of the snowballing process."""

    id: str
    kind: SetKind
    iteration: int
    works: list[Work] = Field(default_factory=list)


class Decision(BaseModel):
    bib_key: str = Field(
        validation_alias=AliasChoices("bib_key", "bib_id"),
        serialization_alias="bib_id",
    )
    researcher_id: str
    verdict: Verdict
    criterion_id: str | None = None
    phase_id: str | None = None
    note: str | None = None
    decided_at: datetime


class Resolution(BaseModel):
    """Final call when researchers disagreed on a work."""

    bib_key: str = Field(
        validation_alias=AliasChoices("bib_key", "bib_id"),
        serialization_alias="bib_id",
    )
    verdict: Verdict
    by: str
    note: str | None = None
    resolved_at: datetime


class Relation(BaseModel):
    """A directed citation edge: `citing_bib_key` cites `cited_bib_key`."""

    citing_bib_key: str
    cited_bib_key: str
