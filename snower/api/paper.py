from fastapi import APIRouter, Depends, HTTPException

from snower.api.project import _summary, get_project
from snower.api.schemas import PaperWithAssessments, ProjectSummary, ScreeningRequest
from snower.paper import Paper
from snower.project import Project
from snower.review import Assessment

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


@router.patch("/{bib_id}", response_model=PaperWithAssessments)
def screen_paper(bib_id: str, body: ScreeningRequest, project: Project = Depends(get_project)):
    """Record a researcher's screening assessment for a paper.

    Requires criterion_id, phase_id, and researcher_email. The include/reject
    meaning is derived from the criterion's type; it is not sent in the body.
    Returns the updated paper including its decision and full assessment map.
    """
    if bib_id not in project.papers:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    try:
        project.assess(
            bib_id,
            criterion_id=body.criterion_id,
            phase_id=body.phase_id,
            researcher_email=body.researcher_email,
            comment=body.comment,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    project.save()
    paper = project.papers[bib_id]
    return PaperWithAssessments(**paper.model_dump(), assessments=project.assessments_of(bib_id))


@router.get("/{bib_id}/assessments", response_model=dict[str, Assessment])
def get_assessments(bib_id: str, project: Project = Depends(get_project)):
    """Get all researcher assessments for a paper (email → Assessment)."""
    if bib_id not in project.papers:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    return project.assessments_of(bib_id)


@router.delete("/{bib_id}/assessments/{researcher_email}", response_model=PaperWithAssessments)
def delete_assessment(bib_id: str, researcher_email: str, project: Project = Depends(get_project)):
    """Remove a researcher's assessment for a paper.

    Returns the updated paper with its recomputed decision and remaining assessments.
    """
    if bib_id not in project.papers:
        raise HTTPException(status_code=404, detail=f"Paper {bib_id!r} not found")
    try:
        project.remove_assessment(bib_id, researcher_email)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    project.save()
    paper = project.papers[bib_id]
    return PaperWithAssessments(**paper.model_dump(), assessments=project.assessments_of(bib_id))


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
