"""Set listing and retrieval endpoints."""

from __future__ import annotations

import pathlib
import tempfile

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile

from snow.api.state import get_repo
from snow.domain.models import Set
from snow.providers.factory import get_enrichment_provider
from snow.storage import bib
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


@router.post("/{set_id}/import", response_model=Set)
async def import_bib(
    set_id: str,
    file: UploadFile,
    repo: ProjectRepo = Depends(get_repo),
    x_researcher_id: str | None = Header(default=None),
) -> Set:
    """Import works from a .bib file upload into an existing set.

    If a researcher is active, decisions are created for works whose `groups`
    field matches a criterion ID.
    """
    if set_id not in repo.list_set_ids():
        raise HTTPException(404, f"Set not found: {set_id}")
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".bib", delete=False) as tmp:
        tmp.write(content)
        tmp_path = pathlib.Path(tmp.name)
    try:
        works = bib.load(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    works = repo.merge_with_library(works)
    works = get_enrichment_provider(repo.load_project()).enrich_works(works)
    criteria = repo.load_project().criteria if x_researcher_id else None
    try:
        return repo.import_bib_to_set(set_id, works, criteria=criteria, researcher_id=x_researcher_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
