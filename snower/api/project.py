import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from snower.api.schemas import (
    ImportRequest,
    ImportResult,
    PaperWithAssessments,
    ProjectSummary,
    ProjectUpdate,
    SetSummary,
)
from snower.bibtex import parse_bibtex
from snower.project import Project


def _load_or_create(path: Path) -> Project:
    """Load the project at path, or create it if it does not exist yet."""
    if (path / Project._METADATA_FILE).exists():
        return Project.load(path)
    project = Project(name=path.name, path=path)
    project.save()
    return project


_project_path: Path | None = None


def _get_path() -> Path:
    global _project_path
    if _project_path is None:
        _project_path = Path(os.environ.get("SNOWER_PROJECT_PATH", "project"))
        _load_or_create(_project_path)  # ensure project.yml exists
    return _project_path


def get_project() -> Project:
    """FastAPI dependency: loads the project from disk on every request.

    The project path is read from ``SNOWER_PROJECT_PATH`` (default: ``./project``).
    Reloading per-request means edits to ``project.yml`` (name, etc.) are always
    picked up without restarting the server.
    """
    return Project.load(_get_path())


def _summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        name=project.name,
        folder=str(project.path.resolve()),
        seeds=sorted(project.seeds),
        sets=[SetSummary.from_paper_set(ps) for ps in project.sets()],
        criteria=list(project.criteria),
        phases=list(project.phases),
        researchers=list(project.researchers),
        decision_strategy=project.decision_strategy.value,
    )


router = APIRouter()


@router.get("/", response_model=ProjectSummary)
def get_project_summary(project: Project = Depends(get_project)):
    """Get a summary of the current project."""
    return _summary(project)


@router.patch("/", response_model=ProjectSummary)
def update_project(body: ProjectUpdate, project: Project = Depends(get_project)):
    """Update project-level settings (currently: decision_strategy)."""
    project.set_decision_strategy(body.decision_strategy)
    project.save()
    return _summary(project)


@router.get("/sets", response_model=list[SetSummary])
def list_sets(project: Project = Depends(get_project)):
    """List all paper sets derived from the citation graph."""
    return [SetSummary.from_paper_set(ps) for ps in project.sets()]


@router.get("/sets/{set_name}/papers", response_model=list[PaperWithAssessments])
def list_papers_in_set(set_name: str, project: Project = Depends(get_project)):
    """List papers in a named set with their full assessment maps."""
    return [
        PaperWithAssessments(**p.model_dump(), assessments=project.assessments_of(p.bib_id))
        for p in project.papers_in(set_name)
    ]


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


