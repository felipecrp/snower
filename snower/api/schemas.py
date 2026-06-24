from pydantic import BaseModel

from snower.project import PaperSet


class ImportRequest(BaseModel):
    bibtex: str
    as_seed: bool = False


class ScreeningRequest(BaseModel):
    included: bool


class ScreeningResult(BaseModel):
    bib_id: str
    included: bool | None


class SetSummary(BaseModel):
    name: str
    round: int | None
    count: int

    @classmethod
    def from_paper_set(cls, ps: PaperSet) -> "SetSummary":
        return cls(name=ps.name, round=ps.round, count=len(ps.paper_ids))


class ProjectSummary(BaseModel):
    name: str
    seeds: list[str]
    sets: list[SetSummary]


class ImportResult(BaseModel):
    imported: list[str]
    skipped: list[str]
