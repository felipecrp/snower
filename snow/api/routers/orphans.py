"""Orphan recalculation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from snow.api.state import get_repo
from snow.domain.models import Set
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/orphans", tags=["orphans"])


@router.post("/recalculate", response_model=list[Set])
def recalculate(repo: ProjectRepo = Depends(get_repo)) -> list[Set]:
    repo.recalculate_orphans()
    return [repo.load_set(sid) for sid in repo.list_set_ids()]
