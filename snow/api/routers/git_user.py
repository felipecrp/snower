"""Git identity endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from snow.git_utils import git_user_email, git_user_name

router = APIRouter(tags=["git"])


class GitUser(BaseModel):
    name: str | None
    email: str | None


@router.get("/api/git-user", response_model=GitUser)
def get_git_user() -> GitUser:
    return GitUser(name=git_user_name(), email=git_user_email())
