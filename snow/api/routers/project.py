"""Project metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from snow.api.state import get_repo
from snow.domain.models import (
    Criterion,
    CriterionKind,
    Phase,
    Project,
    Researcher,
)
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/project", tags=["project"])


class ResearcherInput(BaseModel):
    email: str
    name: str
    previous_email: str | None = None


class CriterionInput(BaseModel):
    id: str
    kind: CriterionKind
    description: str
    previous_id: str | None = None


class PhaseInput(BaseModel):
    id: str
    description: str
    previous_id: str | None = None


class ProjectInfoInput(BaseModel):
    name: str
    description: str | None = None


@router.get("", response_model=Project)
def get_project(repo: ProjectRepo = Depends(get_repo)) -> Project:
    return repo.load_project()


@router.put("/info", response_model=Project)
def update_project_info(
    body: ProjectInfoInput,
    repo: ProjectRepo = Depends(get_repo),
) -> Project:
    project = repo.load_project()
    project.name = body.name.strip()
    project.description = body.description
    repo.save_project(project)
    return project


@router.put("/researchers", response_model=list[Researcher])
def replace_researchers(
    items: list[ResearcherInput],
    repo: ProjectRepo = Depends(get_repo),
) -> list[Researcher]:
    new_emails = [r.email.strip().lower() for r in items]
    if len(set(new_emails)) != len(new_emails):
        raise HTTPException(400, "Researcher emails must be unique")

    existing = repo.list_researchers()
    existing_emails = {r.email for r in existing}
    renames = _collect_renames(items, existing_emails)

    renamed_old_emails = set(renames.keys())
    kept_emails = set(new_emails) | renamed_old_emails
    removed_emails = existing_emails - kept_emails

    if renames:
        _rewrite_researcher_refs(repo, renames)
    if removed_emails:
        _delete_researcher_decisions(repo, removed_emails)
        for email in removed_emails:
            repo.delete_researcher(email)

    for item in items:
        repo.save_researcher(Researcher(email=item.email, name=item.name))

    return repo.list_researchers()


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


@router.put("/phases", response_model=list[Phase])
def replace_phases(
    items: list[PhaseInput],
    repo: ProjectRepo = Depends(get_repo),
) -> list[Phase]:
    new_ids = [p.id for p in items]
    if len(set(new_ids)) != len(new_ids):
        raise HTTPException(400, "Phase ids must be unique")

    project = repo.load_project()
    existing_ids = {p.id for p in project.phases}
    renames = _collect_renames(items, existing_ids)

    project.phases = [Phase(id=p.id, description=p.description) for p in items]
    repo.save_project(project)

    if renames:
        _rewrite_phase_refs(repo, renames)
    return project.phases


def _collect_renames(
    items: list[ResearcherInput] | list[CriterionInput],
    existing_ids: set[str],
) -> dict[str, str]:
    """Map of {previous_id/previous_email -> new_id/email}."""
    renames: dict[str, str] = {}
    for item in items:
        prev = getattr(item, "previous_email", None) or getattr(item, "previous_id", None)
        new = getattr(item, "email", None) or getattr(item, "id", None)
        if prev and prev != new:
            if prev not in existing_ids:
                raise HTTPException(
                    400, f"previous value {prev!r} not found in current list"
                )
            if prev in renames:
                raise HTTPException(
                    400, f"previous value {prev!r} referenced more than once"
                )
            renames[prev] = new
    return renames


def _delete_researcher_decisions(repo: ProjectRepo, removed_emails: set[str]) -> None:
    for set_id in repo.list_set_ids():
        decisions, resolutions = repo.load_decisions(set_id)
        filtered = [d for d in decisions if d.researcher_id not in removed_emails]
        if len(filtered) != len(decisions):
            repo.save_decisions(set_id, filtered, resolutions)


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


def _rewrite_phase_refs(repo: ProjectRepo, renames: dict[str, str]) -> None:
    for set_id in repo.list_set_ids():
        decisions, resolutions = repo.load_decisions(set_id)
        changed = False
        for d in decisions:
            if d.phase_id in renames:
                d.phase_id = renames[d.phase_id]
                changed = True
        if changed:
            repo.save_decisions(set_id, decisions, resolutions)
