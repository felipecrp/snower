"""Global snowballing endpoint.

POST /api/snowballing/{kind}  — runs backward or forward snowballing for ALL
accepted papers that have not been snowballed yet in that direction.

Papers from sets at iteration N feed into a set at iteration N+1. The Google
Scholar provider (scholarly library) is used by default.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from snow.api.state import get_repo
from snow.domain.models import Set, SetKind
from snow.providers.scholarly_provider import ScholarlyProvider
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/snowballing", tags=["snowballing"])

_provider = ScholarlyProvider()


@router.post("/{kind}", response_model=list[Set])
def run_snowballing(
    kind: SetKind,
    repo: ProjectRepo = Depends(get_repo),
) -> list[Set]:
    if kind == SetKind.START:
        raise HTTPException(400, "Snowballing kind must be backward or forward.")
    try:
        return repo.run_global_snowballing(kind, _provider)
    except ValueError as e:
        raise HTTPException(400, str(e))
