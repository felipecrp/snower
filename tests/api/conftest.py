from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from snow.api.app import create_app
from snow.domain.models import (
    Criterion,
    CriterionKind,
    Project,
    Researcher,
    Work,
)
from snow.storage.repo import ProjectRepo


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    repo = ProjectRepo(root)
    repo.init(
        Project(
            name="demo",
            researchers=[
                Researcher(id="alice", name="Alice"),
                Researcher(id="bob", name="Bob"),
            ],
            criteria=[
                Criterion(id="inc1", kind=CriterionKind.INCLUDE, description="empirical"),
                Criterion(id="exc1", kind=CriterionKind.EXCLUDE, description="off-topic"),
            ],
        )
    )
    repo.import_start_set(
        [
            Work(bib_key="", title="Systematic literature review", authors=["Alpha, Aaron"], year=2020, doi="10/alpha"),
            Work(bib_key="", title="Snowballing in software engineering", authors=["Beta, Barbara"], year=2021, doi="10/beta"),
        ]
    )
    return root


@pytest.fixture
def client(project_dir: Path) -> TestClient:
    return TestClient(create_app(project_dir))


@pytest.fixture
def alice_headers() -> dict[str, str]:
    return {"X-Researcher-Id": "alice"}
