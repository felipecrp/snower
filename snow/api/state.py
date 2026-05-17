"""Per-process API state.

The FastAPI app may start bound to a project or with no project at all. When no
project is bound, only the workspace endpoints work; routers that need a repo
get a 409 from `get_repo`. The frontend remembers the last project in
localStorage and reopens it on startup via `POST /api/workspace/open`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, Header, HTTPException, Request

from snow.domain.models import Researcher
from snow.storage.repo import ProjectRepo


class ApiState:
    def __init__(self, project_root: Path | None = None) -> None:
        self.repo: ProjectRepo | None = None
        if project_root is not None:
            candidate = ProjectRepo(project_root)
            if candidate.project_path().exists():
                candidate.ensure_scaffolding()
                self.repo = candidate

    def switch(self, new_root: Path) -> None:
        repo = ProjectRepo(new_root)
        repo.ensure_scaffolding()
        self.repo = repo


def get_state(request: Request) -> ApiState:
    state: ApiState | None = request.app.state.snow
    if state is None:
        raise HTTPException(500, "Server not initialized")
    return state


def get_repo(state: ApiState = Depends(get_state)) -> ProjectRepo:
    if state.repo is None:
        raise HTTPException(409, "No project open")
    return state.repo


def get_active_researcher(
    x_researcher_id: str | None = Header(default=None),
    state: ApiState = Depends(get_state),
) -> Researcher:
    if not x_researcher_id:
        raise HTTPException(401, "Missing X-Researcher-Id header")
    if state.repo is None:
        raise HTTPException(409, "No project open")
    researchers = state.repo.list_researchers()
    for r in researchers:
        if r.email == x_researcher_id:
            return r
    raise HTTPException(403, f"Unknown researcher: {x_researcher_id}")
