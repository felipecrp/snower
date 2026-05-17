"""Tests for /api/workspace, including the no-project bootstrap."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from snow.api.app import create_app


class DescribeWorkspaceWithoutProject:
    def it_returns_null_when_no_project_bound(self):
        client = TestClient(create_app(None))
        r = client.get("/api/workspace")
        assert r.status_code == 200
        assert r.json() is None

    def it_returns_409_for_routes_that_need_a_repo(self):
        client = TestClient(create_app(None))
        r = client.get("/api/sets")
        assert r.status_code == 409

    def it_lets_user_open_a_project_at_runtime(self, tmp_path: Path):
        client = TestClient(create_app(None))
        # No project at first.
        assert client.get("/api/workspace").json() is None
        # Init a fresh project on disk.
        from snow.domain.models import Project
        from snow.storage.repo import ProjectRepo
        root = tmp_path / "proj"
        ProjectRepo(root).init(Project(name="demo"))
        # Open it via the API.
        r = client.post("/api/workspace/open", json={"path": str(root)})
        assert r.status_code == 200
        body = client.get("/api/workspace").json()
        assert body is not None
        assert body["name"] == "demo"

    def it_ensures_start_set_when_opening_a_bare_project(self, tmp_path: Path):
        from snow.domain.models import Project
        from snow.storage import yml
        # Hand-rolled "bare" project on disk: only project.yml, no sets/.
        root = tmp_path / "bare"
        root.mkdir()
        yml.dump(Project(name="bare").model_dump(mode="json", exclude_none=True), root / "project.yml")
        assert not (root / "sets" / "00-start").exists()

        client = TestClient(create_app(None))
        r = client.post("/api/workspace/open", json={"path": str(root)})
        assert r.status_code == 200
        assert (root / "sets" / "00-start" / "set.yml").exists()
        sets = client.get("/api/sets").json()
        assert any(s["id"] == "00-start" for s in sets)

    def it_creates_new_project_with_default_criteria(self, tmp_path: Path):
        client = TestClient(create_app(None))
        root = tmp_path / "new-proj"
        r = client.post("/api/workspace/new", json={"path": str(root), "name": "My Review"})
        assert r.status_code == 200

        # Verify default criteria were created.
        project = client.get("/api/project").json()
        assert len(project["criteria"]) == 9
        criterion_ids = {c["id"] for c in project["criteria"]}
        assert criterion_ids == {"ic1", "ec1", "ec2", "ec3", "ec4", "ec5", "ec6", "ec7", "ec8"}

        # Verify kinds are correct.
        includes = [c for c in project["criteria"] if c["kind"] == "include"]
        excludes = [c for c in project["criteria"] if c["kind"] == "exclude"]
        assert len(includes) == 1
        assert len(excludes) == 8
