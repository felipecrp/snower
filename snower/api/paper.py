from fastapi import APIRouter, Depends, HTTPException

from snower.api.project import _summary, get_project
from snower.api.schemas import ProjectSummary, ScreeningRequest
from snower.paper import Paper
from snower.project import Project

router = APIRouter(prefix="/papers")


@router.get("", response_model=list[Paper])
def list_papers(project: Project = Depends(get_project)):
    """List all papers in the project."""
    return list(project.papers.values())


@router.get("/{bib_id}", response_model=Paper)
def get_paper(bib_id: str, project: Project = Depends(get_project)):
    """Get a single paper by bib_id."""
    paper = project.papers.get(bib_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    return paper


@router.patch("/{bib_id}", response_model=Paper)
def screen_paper(bib_id: str, body: ScreeningRequest, project: Project = Depends(get_project)):
    """Include or exclude a paper (screening)."""
    if bib_id not in project.papers:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    if body.included:
        project.include(bib_id)
    else:
        project.exclude(bib_id)
    project.save()
    return project.papers[bib_id]


@router.post("/{bib_id}/seed", response_model=ProjectSummary)
def add_seed(bib_id: str, project: Project = Depends(get_project)):
    """Mark an existing paper as a seed. Idempotent."""
    paper = project.papers.get(bib_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    project.add_seed(paper)
    project.save()
    return _summary(project)


@router.delete("/{bib_id}/seed", response_model=ProjectSummary)
def remove_seed(bib_id: str, project: Project = Depends(get_project)):
    """Remove a paper from seeds. The paper remains in the project."""
    if bib_id not in project.papers:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    try:
        project.remove_seed(bib_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} is not a seed")
    project.save()
    return _summary(project)
