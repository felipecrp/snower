"""Snow command-line interface."""

from __future__ import annotations

import logging
import socket
import sys
from pathlib import Path

import typer
import uvicorn

from snow.api.app import create_app
from snow.domain.models import Project
from snow.git_utils import git_available, git_user_email, git_user_name
from snow.providers.factory import get_enrichment_provider
from snow.storage import bib
from snow.storage.repo import ProjectRepo

app = typer.Typer(help="Snow — local-first literature review via snowballing.")


@app.command()
def init(
    path: Path = typer.Argument(..., help="Project directory to create."),
    name: str = typer.Option(None, "--name", help="Project name (defaults to dir name)."),
) -> None:
    """Create a new snow project directory."""
    repo = ProjectRepo(path)
    if repo.project_path().exists():
        typer.echo(f"Project already exists at {path}", err=True)
        raise typer.Exit(code=1)
    project = Project(name=name or path.name)
    repo.init(project)
    typer.echo(f"Initialized snow project at {path}")


@app.command("import-bib")
def import_bib(
    bib_path: Path = typer.Argument(..., exists=True, readable=True, help=".bib file to import."),
    project: Path = typer.Option(Path("."), "--project", "-p", help="Project directory."),
) -> None:
    """Import a .bib file as the project's start set (00-start)."""
    repo = ProjectRepo(project)
    if not repo.project_path().exists():
        typer.echo(f"No snow project at {project} — run `snow init` first.", err=True)
        raise typer.Exit(code=1)
    head = bib_path.read_text(encoding="utf-8", errors="replace").lstrip()[:200]
    if not head.startswith("@") and "@" not in head.split("\n", 5)[0]:
        typer.echo(
            f"{bib_path} does not look like BibTeX (no '@entry{{...}}' found near the top).\n"
            "Hint: re-export as plain BibTeX (e.g. Zotero → Format: BibTeX, not Bibliontology RDF).",
            err=True,
        )
        raise typer.Exit(code=1)

    works = bib.load(bib_path)
    if not works:
        typer.echo(f"{bib_path}: parsed 0 entries — file may be empty or malformed.", err=True)
        raise typer.Exit(code=1)
    works = repo.merge_with_library(works)
    works = get_enrichment_provider(repo.load_project(), email=git_user_email()).enrich_works(works)
    start = repo.import_start_set(works)
    typer.echo(f"Imported {len(start.works)} works into {start.id}")


def _configure_logging(project_root: Path | None) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    snow_logger = logging.getLogger("snow")
    snow_logger.setLevel(logging.INFO)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    snow_logger.addHandler(stream)


@app.command()
def serve(
    project: Path | None = typer.Option(None, "--project", "-p", help="Project directory."),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Start the local FastAPI server. With no --project the UI shows the
    workspace dialog and the user picks one (the frontend remembers the last
    used project in localStorage). Use --port 0 to bind to an OS-assigned free port."""
    if project is not None and not (project / "project.yml").exists():
        typer.echo(f"No snow project at {project} — run `snow init` first.", err=True)
        raise typer.Exit(code=1)
    if not git_available():
        typer.echo(
            "Error: git is not installed or not on PATH.\n"
            "Snow requires git to identify researchers. Please install git and try again.",
            err=True,
        )
        raise typer.Exit(code=1)
    if not git_user_name() or not git_user_email():
        typer.echo(
            "Error: git global user identity is not configured.\n"
            "Please run:\n"
            "  git config --global user.name  \"Your Name\"\n"
            "  git config --global user.email \"you@example.com\"",
            err=True,
        )
        raise typer.Exit(code=1)

    if port == 0:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        port = sock.getsockname()[1]
        sock.close()
        typer.echo(f"Listening on http://{host}:{port}")

    _configure_logging(project)
    fastapi_app = create_app(project)
    uvicorn.run(fastapi_app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
