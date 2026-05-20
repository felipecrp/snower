"""Set listing and retrieval endpoints."""

from __future__ import annotations

import pathlib
import tempfile

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, UploadFile

from snow.api.state import get_repo
from snow.domain.models import Set, Work
from snow.providers.factory import get_enrichment_provider
from snow.researcher_log import get_researcher_logger
from snow.storage import bib, tabular
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
    project = repo.load_project()
    works_before = {w.title: dict(doi=w.doi, venue=w.venue, abstract=w.abstract, url=w.url) for w in works}
    works = get_enrichment_provider(project, email=x_researcher_id).enrich_works(works)
    criteria = project.criteria if x_researcher_id else None
    phases = project.phases if x_researcher_id else None
    try:
        updated_set, added, merged = repo.import_bib_to_set(
            set_id, works, criteria=criteria, phases=phases, researcher_id=x_researcher_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if x_researcher_id:
        enriched_count = sum(
            1 for w in works
            for field in ("doi", "venue", "abstract", "url")
            if getattr(w, field) and not works_before.get(w.title, {}).get(field)
        )
        rlog = get_researcher_logger(repo.root, x_researcher_id)
        rlog.info(
            "Import into %s: %d parsed, %d new, %d merged, %d fields enriched",
            set_id, len(works), len(added), len(merged), enriched_count,
        )
        for w in added:
            rlog.info("Added %s", w.bib_key or w.title)
        for w in merged:
            rlog.info("Merged %s", w.bib_key or w.title)

    return updated_set


@router.post("/{set_id}/parse-bib", response_model=list[Work])
async def parse_bib(
    set_id: str,
    file: UploadFile,
    repo: ProjectRepo = Depends(get_repo),
) -> list[Work]:
    """Parse a .bib upload and return individual Work entries without importing."""
    if set_id not in repo.list_set_ids():
        raise HTTPException(404, f"Set not found: {set_id}")
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".bib", delete=False) as tmp:
        tmp.write(content)
        tmp_path = pathlib.Path(tmp.name)
    try:
        return bib.load(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/{set_id}/parse", response_model=list[Work])
async def parse_import(
    set_id: str,
    text: str = Body(..., embed=True),
    format: str = Body(..., embed=True),
    repo: ProjectRepo = Depends(get_repo),
) -> list[Work]:
    """Parse text (BibTeX, CSV, or TSV) and return Work entries without importing."""
    if set_id not in repo.list_set_ids():
        raise HTTPException(404, f"Set not found: {set_id}")
    try:
        if format == "bib":
            return bib.loads(text)
        return tabular.parse(text, format)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{set_id}/import-work", response_model=Work)
async def import_work(
    set_id: str,
    work: Work,
    enrich: bool = Query(default=True),
    repo: ProjectRepo = Depends(get_repo),
    x_researcher_id: str | None = Header(default=None),
    x_active_phase: str | None = Header(default=None),
) -> Work:
    """Import a single Work into a set, running merge + enrichment pipeline.

    When set_id is 'orphan', the work is staged as unplaced and enriched;
    callers should invoke POST /api/orphans/recalculate after the batch.
    """
    project = repo.load_project()
    criteria = project.criteria if x_researcher_id else None
    phases = project.phases if x_researcher_id else None

    if set_id == "orphan":
        works = repo.merge_with_library([work])
        if enrich:
            works = get_enrichment_provider(project, email=x_researcher_id).enrich_works(works)
        try:
            return repo.import_unplaced_work(
                works[0],
                criteria=criteria,
                phases=phases,
                researcher_id=x_researcher_id,
                active_phase=x_active_phase,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    if set_id not in repo.list_set_ids():
        raise HTTPException(404, f"Set not found: {set_id}")
    works = repo.merge_with_library([work])
    if enrich:
        works = get_enrichment_provider(project, email=x_researcher_id).enrich_works(works)
    try:
        updated_set, _, _ = repo.import_bib_to_set(
            set_id, works, criteria=criteria, phases=phases,
            researcher_id=x_researcher_id, active_phase=x_active_phase,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    saved = next((w for w in updated_set.works if w.bib_key == works[0].bib_key), works[0])
    return saved
