from fastapi import APIRouter, Depends, HTTPException, Response

from snower.api.project import get_project
from snower.project import Project
from snower.review import Criterion, Phase, Researcher

router = APIRouter()


# ----- Criteria -----------------------------------------------------------

@router.get("/criteria", response_model=list[Criterion])
def list_criteria(project: Project = Depends(get_project)):
    """List all inclusion/exclusion criteria."""
    return project.criteria


@router.post("/criteria", status_code=201)
def create_criterion(body: Criterion, project: Project = Depends(get_project)):
    """Add a new criterion. Returns 409 if the id already exists."""
    try:
        project.add_criterion(body)
    except ValueError:
        raise HTTPException(status_code=409, detail=f"Criterion {body.id!r} already exists")
    project.save()


@router.patch("/criteria/{id}", status_code=204, response_class=Response)
def update_criterion(id: str, body: Criterion, project: Project = Depends(get_project)):
    """Update a criterion's fields. If body.id differs from the path id, the criterion is renamed first."""
    try:
        if body.id != id:
            project.rename_criterion(id, body.id)
        project.update_criterion(body.id, name=body.name, type=body.type)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Criterion {id!r} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    project.save()
    return Response(status_code=204)


@router.delete("/criteria/{id}", status_code=204, response_class=Response)
def delete_criterion(id: str, project: Project = Depends(get_project)):
    """Remove a criterion."""
    try:
        project.remove_criterion(id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Criterion {id!r} not found")
    project.save()
    return Response(status_code=204)


# ----- Phases -------------------------------------------------------------

@router.get("/phases", response_model=list[Phase])
def list_phases(project: Project = Depends(get_project)):
    """List all reading phases."""
    return project.phases


@router.post("/phases", status_code=201)
def create_phase(body: Phase, project: Project = Depends(get_project)):
    """Add a new phase. Returns 409 if the id already exists."""
    try:
        project.add_phase(body)
    except ValueError:
        raise HTTPException(status_code=409, detail=f"Phase {body.id!r} already exists")
    project.save()


@router.patch("/phases/{id}", status_code=204, response_class=Response)
def update_phase(id: str, body: Phase, project: Project = Depends(get_project)):
    """Update a phase's fields. If body.id differs from the path id, the phase is renamed first."""
    try:
        if body.id != id:
            project.rename_phase(id, body.id)
        project.update_phase(body.id, name=body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Phase {id!r} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    project.save()
    return Response(status_code=204)


@router.delete("/phases/{id}", status_code=204, response_class=Response)
def delete_phase(id: str, project: Project = Depends(get_project)):
    """Remove a phase."""
    try:
        project.remove_phase(id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Phase {id!r} not found")
    project.save()
    return Response(status_code=204)


# ----- Researchers --------------------------------------------------------

@router.get("/researchers", response_model=list[Researcher])
def list_researchers(project: Project = Depends(get_project)):
    """List all registered researchers."""
    return project.researchers


@router.post("/researchers", status_code=201)
def create_researcher(body: Researcher, project: Project = Depends(get_project)):
    """Register a researcher. Returns 409 if the email already exists."""
    try:
        project.add_researcher(body)
    except ValueError:
        raise HTTPException(status_code=409, detail=f"Researcher {body.email!r} already exists")
    project.save()


@router.patch("/researchers/{email}", status_code=204, response_class=Response)
def update_researcher(email: str, body: Researcher, project: Project = Depends(get_project)):
    """Update a researcher's fields. If body.email differs from the path email, the researcher is renamed first."""
    try:
        if body.email != email:
            project.rename_researcher(email, body.email)
        project.update_researcher(body.email, name=body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Researcher {email!r} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    project.save()
    return Response(status_code=204)


@router.delete("/researchers/{email}", status_code=204, response_class=Response)
def delete_researcher(email: str, project: Project = Depends(get_project)):
    """Remove a researcher."""
    try:
        project.remove_researcher(email)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Researcher {email!r} not found")
    project.save()
    return Response(status_code=204)
