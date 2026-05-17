"""Git global config helpers."""

from __future__ import annotations

import subprocess


def _git_config(key: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "config", "--global", key],
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        return value or None
    except FileNotFoundError:
        return None


def git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def git_user_name() -> str | None:
    return _git_config("user.name")


def git_user_email() -> str | None:
    return _git_config("user.email")
