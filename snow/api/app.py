"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from snow.api.routers import bidding, decisions, downloads, git_user, orphans, project, recent_projects, sets, snowballing, workspace
from snow.api.state import ApiState


def create_app(project_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="Snow", version="0.1.0")
    app.state.snow = ApiState(project_root)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(workspace.router)
    app.include_router(git_user.router)
    app.include_router(recent_projects.router)
    app.include_router(project.router)
    app.include_router(sets.router)
    app.include_router(decisions.router)
    app.include_router(snowballing.router)
    app.include_router(orphans.router)
    app.include_router(downloads.router)
    app.include_router(bidding.router)
    return app
