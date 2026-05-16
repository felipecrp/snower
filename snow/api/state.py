"""Per-process API state.

The FastAPI app is bound to a single project on startup. Dependencies
expose the `ProjectRepo` and the active researcher to routers.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, Header, HTTPException, Request

from snow.domain.models import Researcher
from snow.storage.repo import ProjectRepo


class ApiState:
    def __init__(self, project_root: Path) -> None:
        self.repo = ProjectRepo(project_root)
        if not self.repo.project_path().exists():
            raise FileNotFoundError(f"No snow project at {project_root}")


def get_state(request: Request) -> ApiState:
    state: ApiState | None = request.app.state.snow
    if state is None:
        raise HTTPException(500, "Server not bound to a project")
    return state


def get_repo(state: ApiState = Depends(get_state)) -> ProjectRepo:
    return state.repo


def get_active_researcher(
    x_researcher_id: str | None = Header(default=None),
    state: ApiState = Depends(get_state),
) -> Researcher:
    if not x_researcher_id:
        raise HTTPException(401, "Missing X-Researcher-Id header")
    project = state.repo.load_project()
    for r in project.researchers:
        if r.id == x_researcher_id:
            return r
    raise HTTPException(403, f"Unknown researcher id: {x_researcher_id}")
