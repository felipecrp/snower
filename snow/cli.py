"""Snow command-line interface."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
import uvicorn

from snow.api.app import create_app
from snow.domain.models import Project
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
    start = repo.import_start_set(works)
    typer.echo(f"Imported {len(start.works)} works into {start.id}")


def _configure_logging(project_root: Path) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    snow_logger = logging.getLogger("snow")
    snow_logger.setLevel(logging.INFO)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    snow_logger.addHandler(stream)

    log_file = project_root / "snow.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    snow_logger.addHandler(file_handler)


@app.command()
def serve(
    project: Path = typer.Option(Path("."), "--project", "-p", help="Project directory."),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Start the local FastAPI server bound to a project."""
    repo = ProjectRepo(project)
    if not repo.project_path().exists():
        typer.echo(f"No snow project at {project} — run `snow init` first.", err=True)
        raise typer.Exit(code=1)
    _configure_logging(project)
    fastapi_app = create_app(project)
    uvicorn.run(fastapi_app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
