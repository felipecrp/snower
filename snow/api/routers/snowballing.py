"""Global snowballing endpoint.

POST /api/snowballing       — runs backward + forward snowballing for all
POST /api/snowballing/{kind} — runs a single direction

Papers from sets at iteration N feed into a set at iteration N+1.

Provider selection (project.yml):
  providers:
    - name: semantic_scholar   # default; supports optional api_key
    - name: scholarly          # Google Scholar scraper; supports proxy option
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from snow.api.state import get_repo
from snow.domain.models import Set, SetKind
from snow.providers.factory import get_provider
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/snowballing", tags=["snowballing"])


@router.post("", response_model=list[Set])
def run_snowballing_all(
    repo: ProjectRepo = Depends(get_repo),
    x_researcher_id: str | None = Header(default=None),
) -> list[Set]:
    """Run backward then forward snowballing, returning all updated sets."""
    provider = get_provider(repo.load_project(), email=x_researcher_id)
    updated: dict[str, Set] = {}
    for kind in (SetKind.BACKWARD, SetKind.FORWARD):
        for s in repo.run_global_snowballing(kind, provider):
            updated[s.id] = s
    return list(updated.values())


@router.post("/{kind}", response_model=list[Set])
def run_snowballing(
    kind: SetKind,
    force: bool = False,
    repo: ProjectRepo = Depends(get_repo),
    x_researcher_id: str | None = Header(default=None),
) -> list[Set]:
    if kind == SetKind.START:
        raise HTTPException(400, "Snowballing kind must be backward or forward.")
    provider = get_provider(repo.load_project(), email=x_researcher_id)
    try:
        return repo.run_global_snowballing(kind, provider, force=force)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{kind}/{bib_key}", response_model=list[Set])
def run_paper_snowballing(
    kind: SetKind,
    bib_key: str,
    repo: ProjectRepo = Depends(get_repo),
    x_researcher_id: str | None = Header(default=None),
) -> list[Set]:
    """Snowball a single paper. Returns all sets that were created or updated."""
    if kind == SetKind.START:
        raise HTTPException(400, "Snowballing kind must be backward or forward.")
    provider = get_provider(repo.load_project(), email=x_researcher_id)
    try:
        return repo.run_paper_snowballing(kind, bib_key, provider)
    except ValueError as e:
        msg = str(e)
        status = 404 if "not found" in msg else 400
        raise HTTPException(status, msg)
