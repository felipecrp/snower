"""Recent projects endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter

from snow.user_config import RecentProject, load_recent_projects, remember_recent_project, remove_recent_project

router = APIRouter(prefix="/api/recent-projects", tags=["recent-projects"])


class RemoveRecentInput(BaseModel):
    path: str


@router.get("", response_model=list[RecentProject])
def get_recent_projects() -> list[RecentProject]:
    """List recent projects (max 5, most-recent first)."""
    return load_recent_projects()


@router.put("", response_model=list[RecentProject])
def put_recent_project(entry: RecentProject) -> list[RecentProject]:
    """Add or update a recent project."""
    return remember_recent_project(entry)


@router.delete("", response_model=list[RecentProject])
def delete_recent_project(body: RemoveRecentInput) -> list[RecentProject]:
    """Remove a recent project by path."""
    return remove_recent_project(body.path)
