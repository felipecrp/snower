"""Project metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from snow.api.state import get_repo
from snow.domain.models import (
    Criterion,
    CriterionKind,
    Project,
    Researcher,
)
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/project", tags=["project"])


class ResearcherInput(BaseModel):
    id: str
    name: str
    email: str | None = None
    previous_id: str | None = None


class CriterionInput(BaseModel):
    id: str
    kind: CriterionKind
    description: str
    previous_id: str | None = None


@router.get("", response_model=Project)
def get_project(repo: ProjectRepo = Depends(get_repo)) -> Project:
    return repo.load_project()


@router.put("/researchers", response_model=list[Researcher])
def replace_researchers(
    items: list[ResearcherInput],
    repo: ProjectRepo = Depends(get_repo),
) -> list[Researcher]:
    new_ids = [r.id for r in items]
    if len(set(new_ids)) != len(new_ids):
        raise HTTPException(400, "Researcher ids must be unique")

    project = repo.load_project()
    existing_ids = {r.id for r in project.researchers}
    renames = _collect_renames(items, existing_ids)

    project.researchers = [
        Researcher(id=r.id, name=r.name, email=r.email) for r in items
    ]
    repo.save_project(project)

    if renames:
        _rewrite_researcher_refs(repo, renames)
    return project.researchers


@router.put("/criteria", response_model=list[Criterion])
def replace_criteria(
    items: list[CriterionInput],
    repo: ProjectRepo = Depends(get_repo),
) -> list[Criterion]:
    new_ids = [c.id for c in items]
    if len(set(new_ids)) != len(new_ids):
        raise HTTPException(400, "Criterion ids must be unique")

    project = repo.load_project()
    existing_ids = {c.id for c in project.criteria}
    renames = _collect_renames(items, existing_ids)

    project.criteria = [
        Criterion(id=c.id, kind=c.kind, description=c.description) for c in items
    ]
    repo.save_project(project)

    if renames:
        _rewrite_criterion_refs(repo, renames)
    return project.criteria


def _collect_renames(
    items: list[ResearcherInput] | list[CriterionInput],
    existing_ids: set[str],
) -> dict[str, str]:
    """Map of {previous_id -> new_id}. Validates that previous_ids existed."""
    renames: dict[str, str] = {}
    for item in items:
        if item.previous_id and item.previous_id != item.id:
            if item.previous_id not in existing_ids:
                raise HTTPException(
                    400, f"previous_id {item.previous_id!r} not found in current list"
                )
            if item.previous_id in renames:
                raise HTTPException(
                    400, f"previous_id {item.previous_id!r} referenced more than once"
                )
            renames[item.previous_id] = item.id
    return renames


def _rewrite_researcher_refs(repo: ProjectRepo, renames: dict[str, str]) -> None:
    for set_id in repo.list_set_ids():
        decisions, resolutions = repo.load_decisions(set_id)
        changed = False
        for d in decisions:
            if d.researcher_id in renames:
                d.researcher_id = renames[d.researcher_id]
                changed = True
        for r in resolutions:
            if r.by in renames:
                r.by = renames[r.by]
                changed = True
        if changed:
            repo.save_decisions(set_id, decisions, resolutions)


def _rewrite_criterion_refs(repo: ProjectRepo, renames: dict[str, str]) -> None:
    for set_id in repo.list_set_ids():
        decisions, resolutions = repo.load_decisions(set_id)
        changed = False
        for d in decisions:
            if d.criterion_id in renames:
                d.criterion_id = renames[d.criterion_id]
                changed = True
        if changed:
            repo.save_decisions(set_id, decisions, resolutions)
