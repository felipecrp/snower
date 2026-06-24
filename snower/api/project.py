import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from snower.api.schemas import (
    ImportRequest,
    ImportResult,
    ProjectSummary,
    SetSummary,
)
from snower.bibtex import parse_bibtex
from snower.project import PaperSet, Project


def _load_or_create(path: Path) -> Project:
    """Load the project at path, or create it if it does not exist yet."""
    if (path / Project._METADATA_FILE).exists():
        return Project.load(path)
    project = Project(name=path.name, path=path)
    project.save()
    return project


_project: Project | None = None


def get_project() -> Project:
    """FastAPI dependency that returns the single project for this server instance.

    The project path is read from ``SNOWER_PROJECT_PATH`` (default: ``./project``).
    The project is loaded once and cached for the lifetime of the process.
    """
    global _project
    if _project is None:
        path = Path(os.environ.get("SNOWER_PROJECT_PATH", "project"))
        _project = _load_or_create(path)
    return _project


def _summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        name=project.name,
        seeds=sorted(project.seeds),
        sets=[SetSummary.from_paper_set(ps) for ps in project.sets()],
    )


router = APIRouter()


@router.get("/", response_model=ProjectSummary)
def get_project_summary(project: Project = Depends(get_project)):
    """Get a summary of the current project."""
    return _summary(project)


@router.get("/sets", response_model=list[PaperSet])
def list_sets(project: Project = Depends(get_project)):
    """List all paper sets derived from the citation graph."""
    return project.sets()


@router.get("/sets/{set_name}/papers", response_model=list)
def list_papers_in_set(set_name: str, project: Project = Depends(get_project)):
    """List papers in a named set (e.g. ``start-0``, ``backward-1``)."""
    return project.papers_in(set_name)


@router.post("/import", response_model=ImportResult)
def import_bibtex(body: ImportRequest, project: Project = Depends(get_project)):
    """Import papers from a BibTeX string. Use as_seed=true to register them as seeds."""
    try:
        papers = parse_bibtex(body.bibtex)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"BibTeX parse error: {exc}")

    imported: list[str] = []
    skipped: list[str] = []
    for paper in papers:
        if paper.bib_id is None:
            skipped.append(paper.title or "(untitled)")
            continue
        try:
            if body.as_seed:
                project.add_seed(paper)
            else:
                project.add_paper(paper)
            imported.append(paper.bib_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    project.save()
    return ImportResult(imported=imported, skipped=skipped)


