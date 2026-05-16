from datetime import datetime, timezone

from fastapi.testclient import TestClient

from snow.domain.models import Decision, Resolution, Verdict
from snow.storage.repo import ProjectRepo


class DescribeGetProject:
    def it_returns_project_metadata(self, client: TestClient):
        r = client.get("/api/project")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "demo"
        assert [r["id"] for r in body["researchers"]] == ["alice", "bob"]
        assert [c["id"] for c in body["criteria"]] == ["inc1", "exc1"]


class DescribeReplaceResearchers:
    def it_replaces_the_list(self, client: TestClient):
        new_list = [
            {"id": "carol", "name": "Carol", "email": "carol@example.com"},
            {"id": "dave", "name": "Dave"},
        ]
        r = client.put("/api/project/researchers", json=new_list)
        assert r.status_code == 200
        assert [x["id"] for x in r.json()] == ["carol", "dave"]

        body = client.get("/api/project").json()
        assert [x["id"] for x in body["researchers"]] == ["carol", "dave"]
        assert body["name"] == "demo"  # other fields preserved

    def it_rejects_duplicate_ids(self, client: TestClient):
        r = client.put(
            "/api/project/researchers",
            json=[{"id": "x", "name": "A"}, {"id": "x", "name": "B"}],
        )
        assert r.status_code == 400


class DescribeReplaceCriteria:
    def it_replaces_the_list(self, client: TestClient):
        new_list = [
            {"id": "i1", "kind": "include", "description": "peer-reviewed"},
            {"id": "e1", "kind": "exclude", "description": "non-english"},
        ]
        r = client.put("/api/project/criteria", json=new_list)
        assert r.status_code == 200
        body = client.get("/api/project").json()
        assert [c["id"] for c in body["criteria"]] == ["i1", "e1"]
        assert [c["kind"] for c in body["criteria"]] == ["include", "exclude"]

    def it_rejects_duplicate_ids(self, client: TestClient):
        r = client.put(
            "/api/project/criteria",
            json=[
                {"id": "x", "kind": "include", "description": "a"},
                {"id": "x", "kind": "exclude", "description": "b"},
            ],
        )
        assert r.status_code == 400


def _seed_decision(project_dir, researcher_id: str, criterion_id: str | None = "inc1"):
    repo = ProjectRepo(project_dir)
    decisions = [
        Decision(
            work_id="sha1:7775895baced66ce",
            researcher_id=researcher_id,
            verdict=Verdict.ACCEPT,
            criterion_id=criterion_id,
            decided_at=datetime.now(timezone.utc),
        )
    ]
    repo.save_decisions("00-start", decisions, [])


def _seed_resolution(project_dir, by: str):
    repo = ProjectRepo(project_dir)
    decisions, resolutions = repo.load_decisions("00-start")
    resolutions.append(
        Resolution(
            work_id="sha1:7775895baced66ce",
            verdict=Verdict.ACCEPT,
            by=by,
            resolved_at=datetime.now(timezone.utc),
        )
    )
    repo.save_decisions("00-start", decisions, resolutions)


class DescribeRenameResearcher:
    def it_propagates_id_change_to_decisions(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice")
        r = client.put(
            "/api/project/researchers",
            json=[
                {"id": "alice_smith", "name": "Alice", "previous_id": "alice"},
                {"id": "bob", "name": "Bob"},
            ],
        )
        assert r.status_code == 200
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert [d["researcher_id"] for d in decisions] == ["alice_smith"]

    def it_propagates_id_change_to_resolution_by(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice")
        _seed_resolution(project_dir, by="alice")
        client.put(
            "/api/project/researchers",
            json=[
                {"id": "alice_smith", "name": "Alice", "previous_id": "alice"},
                {"id": "bob", "name": "Bob"},
            ],
        )
        resolutions = client.get("/api/sets/00-start/decisions").json()["resolutions"]
        assert [r["by"] for r in resolutions] == ["alice_smith"]

    def it_leaves_non_researcher_resolutions_alone(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice")
        _seed_resolution(project_dir, by="vote")
        client.put(
            "/api/project/researchers",
            json=[
                {"id": "alice_smith", "name": "Alice", "previous_id": "alice"},
                {"id": "bob", "name": "Bob"},
            ],
        )
        resolutions = client.get("/api/sets/00-start/decisions").json()["resolutions"]
        assert resolutions[0]["by"] == "vote"

    def it_rejects_unknown_previous_id(self, client: TestClient):
        r = client.put(
            "/api/project/researchers",
            json=[
                {"id": "x", "name": "X", "previous_id": "ghost"},
                {"id": "bob", "name": "Bob"},
            ],
        )
        assert r.status_code == 400


class DescribeRemoveResearcher:
    def it_deletes_their_decisions_across_all_sets(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice")
        _seed_decision(project_dir, researcher_id="bob")
        r = client.put(
            "/api/project/researchers",
            json=[{"id": "bob", "name": "Bob"}],
        )
        assert r.status_code == 200
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert [d["researcher_id"] for d in decisions] == ["bob"]

    def it_leaves_resolutions_intact(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice")
        _seed_resolution(project_dir, by="alice")
        client.put("/api/project/researchers", json=[{"id": "bob", "name": "Bob"}])
        resolutions = client.get("/api/sets/00-start/decisions").json()["resolutions"]
        assert len(resolutions) == 1


class DescribeRenameCriterion:
    def it_propagates_id_change_to_decisions(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice", criterion_id="inc1")
        r = client.put(
            "/api/project/criteria",
            json=[
                {
                    "id": "empirical",
                    "kind": "include",
                    "description": "empirical",
                    "previous_id": "inc1",
                },
                {"id": "exc1", "kind": "exclude", "description": "off-topic"},
            ],
        )
        assert r.status_code == 200
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert [d["criterion_id"] for d in decisions] == ["empirical"]
