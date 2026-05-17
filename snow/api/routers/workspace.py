"""Workspace endpoints — open or create a project at runtime."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from snow.api.state import ApiState, get_state
from snow.domain.models import Project, Researcher
from snow.git_utils import git_user_email, git_user_name

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceInfo(BaseModel):
    path: str
    name: str
    researcher_email: str | None = None


class NewProjectInput(BaseModel):
    path: str
    name: str
    description: str | None = None


class OpenProjectInput(BaseModel):
    path: str


def _ensure_git_researcher(repo, email: str, name: str) -> None:
    """Create researcher from git identity if not already present."""
    from snow.storage.repo import ProjectRepo
    existing = {r.email for r in repo.list_researchers()}
    if email not in existing:
        repo.save_researcher(Researcher(email=email, name=name or email))


@router.get("", response_model=WorkspaceInfo | None)
def get_workspace(state: ApiState = Depends(get_state)) -> WorkspaceInfo | None:
    if state.repo is None:
        return None
    project = state.repo.load_project()
    researcher_email = git_user_email()
    return WorkspaceInfo(path=str(state.repo.root), name=project.name, researcher_email=researcher_email)


@router.post("/new", response_model=WorkspaceInfo)
def new_project(body: NewProjectInput, state: ApiState = Depends(get_state)) -> WorkspaceInfo:
    root = Path(body.path).expanduser().resolve()
    if root.exists() and (root / "project.yml").exists():
        raise HTTPException(400, f"A snow project already exists at {root}")
    from snow.storage.repo import ProjectRepo
    repo = ProjectRepo(root)
    project = Project(name=body.name.strip() or root.name, description=body.description)
    repo.init(project)
    state.switch(root)
    email = git_user_email()
    name = git_user_name()
    if email:
        _ensure_git_researcher(repo, email, name or email)
    return WorkspaceInfo(path=str(root), name=project.name, researcher_email=email)


@router.post("/open", response_model=WorkspaceInfo)
def open_project(body: OpenProjectInput, state: ApiState = Depends(get_state)) -> WorkspaceInfo:
    root = Path(body.path).expanduser().resolve()
    from snow.storage.repo import ProjectRepo
    repo = ProjectRepo(root)
    if not repo.project_path().exists():
        raise HTTPException(404, f"No snow project at {root}")
    state.switch(root)
    project = repo.load_project()
    email = git_user_email()
    name = git_user_name()
    if email:
        _ensure_git_researcher(repo, email, name or email)
    return WorkspaceInfo(path=str(root), name=project.name, researcher_email=email)
