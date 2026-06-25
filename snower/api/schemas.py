from pydantic import BaseModel

from snower.decision import DecisionStrategyType
from snower.paper import Paper
from snower.project import PaperSet
from snower.review import Assessment, Criterion, Phase, Researcher


class ImportRequest(BaseModel):
    bibtex: str
    as_seed: bool = False


class ScreeningRequest(BaseModel):
    """Body for PATCH /papers/{bib_id}: records a researcher's screening opinion."""

    criterion_id: str
    phase_id: str
    researcher_email: str
    comment: str | None = None


class SetSummary(BaseModel):
    name: str
    round: int | None
    count: int

    @classmethod
    def from_paper_set(cls, ps: PaperSet) -> "SetSummary":
        return cls(name=ps.name, round=ps.round, count=len(ps.paper_ids))


class ProjectSummary(BaseModel):
    name: str
    folder: str
    seeds: list[str]
    sets: list[SetSummary]
    criteria: list[Criterion] = []
    phases: list[Phase] = []
    researchers: list[Researcher] = []
    decision_strategy: str = "majority"


class ProjectUpdate(BaseModel):
    decision_strategy: DecisionStrategyType


class PaperWithAssessments(Paper):
    """A paper augmented with its full assessment map (email → Assessment)."""

    assessments: dict[str, Assessment] = {}


class ImportResult(BaseModel):
    imported: list[str]
    skipped: list[str]

