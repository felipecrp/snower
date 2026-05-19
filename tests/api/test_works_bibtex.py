"""Tests for GET/PUT /api/works/{bib_key}/bibtex."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from snow.api.app import create_app
from snow.domain.models import Project, Work
from snow.storage.repo import ProjectRepo


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    repo = ProjectRepo(root)
    repo.init(Project(name="test"))
    repo.import_start_set([
        Work(bib_key="", title="Systematic review approach", authors=["Smith, John"], year=2020),
    ])
    return root


@pytest.fixture
def client(project_dir: Path) -> TestClient:
    return TestClient(create_app(project_dir))


@pytest.fixture
def bib_key(project_dir: Path) -> str:
    repo = ProjectRepo(project_dir)
    keys = repo.load_keys()
    return next(iter(keys.values())).bib_key


class DescribeGetBibtex:
    def it_returns_raw_bibtex_for_existing_work(self, client: TestClient, bib_key: str):
        r = client.get(f"/api/works/{bib_key}/bibtex")
        assert r.status_code == 200
        body = r.json()
        assert "bibtex" in body
        assert "@" in body["bibtex"]
        assert bib_key in body["bibtex"]

    def it_returns_404_for_unknown_bib_key(self, client: TestClient):
        r = client.get("/api/works/nonexistent2099paper/bibtex")
        assert r.status_code == 404


class DescribePutBibtex:
    def it_persists_edits_and_preserves_bib_key(self, client: TestClient, bib_key: str, project_dir: Path):
        new_bibtex = f"@article{{{bib_key},\n  title = {{Updated Title Here}},\n  author = {{Smith, John}},\n  year = {{2020}}\n}}\n"
        r = client.put(f"/api/works/{bib_key}/bibtex", json={"bibtex": new_bibtex})
        assert r.status_code == 200
        body = r.json()
        assert body["bib_key"] == bib_key
        assert body["title"] == "Updated Title Here"

        repo = ProjectRepo(project_dir)
        work = repo.load_work(bib_key)
        assert work is not None
        assert work.bib_key == bib_key
        assert work.title == "Updated Title Here"

    def it_adds_new_fingerprint_to_keys_yml_when_identity_fields_change(
        self, client: TestClient, bib_key: str, project_dir: Path
    ):
        repo = ProjectRepo(project_dir)
        keys_before = repo.load_keys()
        count_before = len(keys_before)

        new_bibtex = f"@article{{{bib_key},\n  title = {{Completely Different Title}},\n  author = {{Jones, Alice}},\n  year = {{2021}}\n}}\n"
        r = client.put(f"/api/works/{bib_key}/bibtex", json={"bibtex": new_bibtex})
        assert r.status_code == 200

        keys_after = repo.load_keys()
        assert len(keys_after) > count_before
        matching = [e for e in keys_after.values() if e.bib_key == bib_key]
        assert len(matching) >= 2

    def it_rejects_syntactically_invalid_bibtex_with_400(self, client: TestClient, bib_key: str):
        r = client.put(f"/api/works/{bib_key}/bibtex", json={"bibtex": "this is not bibtex {"})
        assert r.status_code == 400
        body = r.json()
        assert body["detail"]["error"] == "parse"

    def it_overwrites_id_in_payload_to_match_path_bib_key(
        self, client: TestClient, bib_key: str, project_dir: Path
    ):
        wrong_key_bibtex = "@article{wrongkey2000wrong,\n  title = {{Some Valid Title}},\n  author = {{Doe, Jane}},\n  year = {{2000}}\n}\n"
        r = client.put(f"/api/works/{bib_key}/bibtex", json={"bibtex": wrong_key_bibtex})
        assert r.status_code == 200
        body = r.json()
        assert body["bib_key"] == bib_key

        repo = ProjectRepo(project_dir)
        work = repo.load_work(bib_key)
        assert work is not None
        assert work.bib_key == bib_key
