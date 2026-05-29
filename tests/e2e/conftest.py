from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from snow.api.app import create_app
from snow.domain.models import BibliographicWork, Criterion, CriterionKind, Project, Researcher
from snow.storage.repo import ProjectRepo


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    repo = ProjectRepo(root)
    repo.init(
        Project(
            name="E2E Review",
            criteria=[
                Criterion(id="inc1", kind=CriterionKind.INCLUDE, description="empirical study"),
                Criterion(id="exc1", kind=CriterionKind.EXCLUDE, description="off-topic"),
            ],
        )
    )
    repo.save_researcher(Researcher(email="alice@example.com", name="Alice"))
    repo.save_researcher(Researcher(email="bob@example.com", name="Bob"))
    return root


@pytest.fixture
def client(project_dir: Path) -> TestClient:
    return TestClient(create_app(project_dir))


@pytest.fixture
def alice() -> dict[str, str]:
    return {"X-Researcher-Id": "alice@example.com"}


@pytest.fixture
def bob() -> dict[str, str]:
    return {"X-Researcher-Id": "bob@example.com"}


def import_work(client: TestClient, set_id: str, title: str, year: int = 2020) -> str:
    """Import a single work without enrichment and return its bib_key."""
    r = client.post(
        f"/api/sets/{set_id}/import-work?enrich=false",
        json={"bib_key": "", "title": title, "authors": ["Author, A"], "year": year},
    )
    assert r.status_code == 200, r.text
    return r.json()["bib_key"]


def decide(
    client: TestClient,
    set_id: str,
    bib_key: str,
    verdict: str,
    criterion_id: str,
    headers: dict[str, str],
) -> None:
    r = client.put(
        f"/api/sets/{set_id}/decisions/{bib_key}",
        json={"verdict": verdict, "criterion_id": criterion_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def mock_provider(
    references: list[BibliographicWork] | None = None,
    citations: list[BibliographicWork] | None = None,
) -> MagicMock:
    """Return a mock Provider with fixed fetch_references / fetch_citations results."""
    p = MagicMock()
    p.fetch_references.return_value = references or []
    p.fetch_citations.return_value = citations or []
    p.enrich_works.side_effect = lambda works: works
    return p
