"""PDF serving endpoint for cached downloads."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from snow.api.state import get_repo
from snow.storage.repo import ProjectRepo

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.get("/{bib_key}")
def get_pdf(bib_key: str, repo: ProjectRepo = Depends(get_repo)) -> FileResponse:
    """Serve local PDF file in browser."""
    path = repo.pdf_path(bib_key)
    if not path.exists():
        raise HTTPException(404, "PDF not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",
    )
