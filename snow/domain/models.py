"""Domain models for snow.

These Pydantic models describe everything persisted in a project directory.
They are designed to round-trip cleanly to .bib + .yml files on disk.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SetKind(StrEnum):
    START = "start"
    BACKWARD = "backward"
    FORWARD = "forward"


class CriterionKind(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


class Verdict(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class Researcher(BaseModel):
    id: str
    name: str
    email: str | None = None


class Criterion(BaseModel):
    id: str
    kind: CriterionKind
    description: str


class ProviderConfig(BaseModel):
    name: str
    enabled: bool = True
    options: dict[str, str] = Field(default_factory=dict)


class Project(BaseModel):
    name: str
    description: str | None = None
    researchers: list[Researcher] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    providers: list[ProviderConfig] = Field(default_factory=list)


class Work(BaseModel):
    """A bibliographic entry as it appears inside a set."""

    id: str
    bib_key: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)
    last_backward_snowballed_at: datetime | None = None
    last_forward_snowballed_at: datetime | None = None


class Set(BaseModel):
    """One iteration of the snowballing process."""

    id: str
    kind: SetKind
    iteration: int
    parent_set_id: str | None = None
    works: list[Work] = Field(default_factory=list)


class Decision(BaseModel):
    work_id: str
    researcher_id: str
    verdict: Verdict
    criterion_id: str | None = None
    note: str | None = None
    decided_at: datetime


class Resolution(BaseModel):
    """Final call when researchers disagreed on a work."""

    work_id: str
    verdict: Verdict
    by: str
    note: str | None = None
    resolved_at: datetime


class Relation(BaseModel):
    """A directed citation edge: `citing_work_id` cites `cited_work_id`."""

    citing_work_id: str
    cited_work_id: str
