"""User-scoped configuration stored in ~/.snower/."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from snow.storage import yml

RECENT_PROJECTS_PATH = Path.home() / ".snower" / "recent-projects.yaml"


class RecentProject(BaseModel):
    path: str
    name: str
    description: str | None = None


def load_recent_projects() -> list[RecentProject]:
    """Load recent projects from ~/.snower/recent-projects.yaml.

    Silently drops any entries whose path no longer contains a project.yml.
    """
    data = yml.load(RECENT_PROJECTS_PATH)
    if not data:
        return []
    recents = [RecentProject(**item) for item in data]
    valid = [r for r in recents if (Path(r.path) / "project.yml").exists()]
    return valid


def remember_recent_project(entry: RecentProject) -> list[RecentProject]:
    """Add/update a recent project and persist the list (max 5, most-recent first)."""
    recents = load_recent_projects()
    next_list = [r for r in recents if r.path != entry.path]
    next_list.insert(0, entry)
    if len(next_list) > 5:
        next_list = next_list[:5]

    RECENT_PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    yml.dump([item.model_dump(exclude_none=True) for item in next_list], RECENT_PROJECTS_PATH)
    return next_list


def remove_recent_project(path: str) -> list[RecentProject]:
    """Remove a recent project by path and persist."""
    recents = load_recent_projects()
    next_list = [r for r in recents if r.path != path]

    RECENT_PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    yml.dump([item.model_dump(exclude_none=True) for item in next_list], RECENT_PROJECTS_PATH)
    return next_list
