"""Decision endpoints for a set."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from snow.api.state import get_active_researcher, get_repo
from snow.domain.models import Decision, Researcher, Resolution, Verdict
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/sets/{set_id}/decisions", tags=["decisions"])


class DecisionsResponse(BaseModel):
    decisions: list[Decision]
    resolutions: list[Resolution]


class DecisionInput(BaseModel):
    verdict: Verdict
    criterion_id: str | None = None
    phase_id: str | None = None
    note: str | None = None


def _ensure_set_exists(repo: ProjectRepo, set_id: str) -> None:
    if set_id not in repo.list_set_ids():
        raise HTTPException(404, f"Set not found: {set_id}")


@router.get("", response_model=DecisionsResponse)
def get_decisions(set_id: str, repo: ProjectRepo = Depends(get_repo)) -> DecisionsResponse:
    _ensure_set_exists(repo, set_id)
    decisions, resolutions = repo.load_decisions(set_id)
    return DecisionsResponse(decisions=decisions, resolutions=resolutions)


@router.put("/{bib_key:path}", response_model=Decision)
def upsert_decision(
    set_id: str,
    bib_key: str,
    body: DecisionInput,
    repo: ProjectRepo = Depends(get_repo),
    researcher: Researcher = Depends(get_active_researcher),
) -> Decision:
    _ensure_set_exists(repo, set_id)
    new_decision = Decision(
        bib_key=bib_key,
        researcher_id=researcher.email,
        verdict=body.verdict,
        criterion_id=body.criterion_id,
        phase_id=body.phase_id,
        note=body.note,
        decided_at=datetime.now(timezone.utc),
    )
    repo.save_researcher_decision(set_id, new_decision)
    return new_decision


@router.delete("/{bib_key:path}", status_code=204)
def delete_decision(
    set_id: str,
    bib_key: str,
    repo: ProjectRepo = Depends(get_repo),
    researcher: Researcher = Depends(get_active_researcher),
) -> None:
    _ensure_set_exists(repo, set_id)
    repo.delete_researcher_decision(set_id, bib_key, researcher.email)
