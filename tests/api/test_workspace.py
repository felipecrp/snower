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
