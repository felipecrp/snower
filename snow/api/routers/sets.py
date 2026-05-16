"""Set listing and retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from snow.api.state import get_repo
from snow.domain.models import Set, SetKind
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/sets", tags=["sets"])


@router.get("", response_model=list[Set])
def list_sets(repo: ProjectRepo = Depends(get_repo)) -> list[Set]:
    return [repo.load_set(sid) for sid in repo.list_set_ids()]


@router.get("/{set_id}", response_model=Set)
def get_set(set_id: str, repo: ProjectRepo = Depends(get_repo)) -> Set:
    try:
        return repo.load_set(set_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, f"Set not found: {set_id}")


@router.post("/{set_id}/snowballing/{kind}", response_model=Set, status_code=201)
def start_snowballing(
    set_id: str,
    kind: SetKind,
    repo: ProjectRepo = Depends(get_repo),
) -> Set:
    if kind == SetKind.START:
        raise HTTPException(400, "Snowballing kind must be backward or forward.")
    try:
        return repo.start_snowballing(set_id, kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, f"Set not found: {set_id}")
