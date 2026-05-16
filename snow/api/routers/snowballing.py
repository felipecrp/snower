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

from fastapi import APIRouter, Depends, HTTPException

from snow.api.state import get_repo
from snow.domain.models import Project, Set, SetKind
from snow.providers.base import Provider
from snow.providers.openalex_provider import OpenAlexProvider
from snow.providers.scholarly_provider import ScholarlyProvider
from snow.providers.semantic_scholar_provider import SemanticScholarProvider
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/snowballing", tags=["snowballing"])


def _get_provider(project: Project) -> Provider:
    for cfg in project.providers:
        if not cfg.enabled:
            continue
        if cfg.name == "scholarly":
            return ScholarlyProvider(options=dict(cfg.options))
        if cfg.name == "semantic_scholar":
            return SemanticScholarProvider(api_key=cfg.options.get("api_key") or None)
        if cfg.name == "openalex":
            return OpenAlexProvider(email=cfg.options.get("email") or None)
    return OpenAlexProvider()


@router.post("", response_model=list[Set])
def run_snowballing_all(repo: ProjectRepo = Depends(get_repo)) -> list[Set]:
    """Run backward then forward snowballing, returning all updated sets."""
    provider = _get_provider(repo.load_project())
    updated: dict[str, Set] = {}
    for kind in (SetKind.BACKWARD, SetKind.FORWARD):
        for s in repo.run_global_snowballing(kind, provider):
            updated[s.id] = s
    return list(updated.values())


@router.post("/{kind}", response_model=list[Set])
def run_snowballing(
    kind: SetKind,
    repo: ProjectRepo = Depends(get_repo),
) -> list[Set]:
    if kind == SetKind.START:
        raise HTTPException(400, "Snowballing kind must be backward or forward.")
    provider = _get_provider(repo.load_project())
    try:
        return repo.run_global_snowballing(kind, provider)
    except ValueError as e:
        raise HTTPException(400, str(e))
