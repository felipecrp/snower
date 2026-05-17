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
        emails = [r["email"] for r in body["researchers"]]
        assert "alice@example.com" in emails
        assert "bob@example.com" in emails
        assert [c["id"] for c in body["criteria"]] == ["inc1", "exc1"]


class DescribeReplaceResearchers:
    def it_replaces_the_list(self, client: TestClient):
        new_list = [
            {"email": "carol@example.com", "name": "Carol"},
            {"email": "dave@example.com", "name": "Dave"},
        ]
        r = client.put("/api/project/researchers", json=new_list)
        assert r.status_code == 200
        assert {x["email"] for x in r.json()} == {"carol@example.com", "dave@example.com"}

        body = client.get("/api/project").json()
        assert {x["email"] for x in body["researchers"]} == {"carol@example.com", "dave@example.com"}
        assert body["name"] == "demo"  # other fields preserved

    def it_rejects_duplicate_emails(self, client: TestClient):
        r = client.put(
            "/api/project/researchers",
            json=[{"email": "x@x.com", "name": "A"}, {"email": "x@x.com", "name": "B"}],
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


def _seed_decision(project_dir, researcher_id: str = "alice@example.com", criterion_id: str | None = "inc1"):
    repo = ProjectRepo(project_dir)
    decisions = [
        Decision(
            bib_key="alpha2020systematic",
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
            bib_key="alpha2020systematic",
            verdict=Verdict.ACCEPT,
            by=by,
            resolved_at=datetime.now(timezone.utc),
        )
    )
    repo.save_decisions("00-start", decisions, resolutions)


class DescribeRenameResearcher:
    def it_propagates_email_change_to_decisions(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice@example.com")
        r = client.put(
            "/api/project/researchers",
            json=[
                {"email": "alice.smith@example.com", "name": "Alice", "previous_email": "alice@example.com"},
                {"email": "bob@example.com", "name": "Bob"},
            ],
        )
        assert r.status_code == 200
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert [d["researcher_id"] for d in decisions] == ["alice.smith@example.com"]

    def it_propagates_email_change_to_resolution_by(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice@example.com")
        _seed_resolution(project_dir, by="alice@example.com")
        client.put(
            "/api/project/researchers",
            json=[
                {"email": "alice.smith@example.com", "name": "Alice", "previous_email": "alice@example.com"},
                {"email": "bob@example.com", "name": "Bob"},
            ],
        )
        resolutions = client.get("/api/sets/00-start/decisions").json()["resolutions"]
        assert [r["by"] for r in resolutions] == ["alice.smith@example.com"]

    def it_leaves_non_researcher_resolutions_alone(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice@example.com")
        _seed_resolution(project_dir, by="vote")
        client.put(
            "/api/project/researchers",
            json=[
                {"email": "alice.smith@example.com", "name": "Alice", "previous_email": "alice@example.com"},
                {"email": "bob@example.com", "name": "Bob"},
            ],
        )
        resolutions = client.get("/api/sets/00-start/decisions").json()["resolutions"]
        assert resolutions[0]["by"] == "vote"

    def it_rejects_unknown_previous_email(self, client: TestClient):
        r = client.put(
            "/api/project/researchers",
            json=[
                {"email": "x@x.com", "name": "X", "previous_email": "ghost@example.com"},
                {"email": "bob@example.com", "name": "Bob"},
            ],
        )
        assert r.status_code == 400


class DescribeRemoveResearcher:
    def it_deletes_their_decisions_across_all_sets(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice@example.com")
        _seed_decision(project_dir, researcher_id="bob@example.com")
        r = client.put(
            "/api/project/researchers",
            json=[{"email": "bob@example.com", "name": "Bob"}],
        )
        assert r.status_code == 200
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert [d["researcher_id"] for d in decisions] == ["bob@example.com"]

    def it_leaves_resolutions_intact(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice@example.com")
        _seed_resolution(project_dir, by="alice@example.com")
        client.put("/api/project/researchers", json=[{"email": "bob@example.com", "name": "Bob"}])
        resolutions = client.get("/api/sets/00-start/decisions").json()["resolutions"]
        assert len(resolutions) == 1


class DescribeReplacePhases:
    def it_replaces_the_list(self, client: TestClient):
        new_list = [
            {"id": "ph1", "description": "Records"},
            {"id": "ph2", "description": "Full text"},
        ]
        r = client.put("/api/project/phases", json=new_list)
        assert r.status_code == 200
        body = client.get("/api/project").json()
        assert [p["id"] for p in body["phases"]] == ["ph1", "ph2"]

    def it_rejects_duplicate_ids(self, client: TestClient):
        r = client.put(
            "/api/project/phases",
            json=[
                {"id": "ph1", "description": "a"},
                {"id": "ph1", "description": "b"},
            ],
        )
        assert r.status_code == 400

    def it_persists_empty_list(self, client: TestClient):
        client.put("/api/project/phases", json=[{"id": "ph1", "description": "Records"}])
        r = client.put("/api/project/phases", json=[])
        assert r.status_code == 200
        assert client.get("/api/project").json()["phases"] == []


def _seed_decision_with_phase(
    project_dir, researcher_id: str = "alice@example.com", phase_id: str | None = "ph1"
):
    repo = ProjectRepo(project_dir)
    decisions = [
        Decision(
            bib_key="alpha2020systematic",
            researcher_id=researcher_id,
            verdict=Verdict.ACCEPT,
            criterion_id="inc1",
            phase_id=phase_id,
            decided_at=datetime.now(timezone.utc),
        )
    ]
    repo.save_decisions("00-start", decisions, [])


class DescribeRenamePhase:
    def it_propagates_id_change_to_decisions(self, client: TestClient, project_dir):
        client.put(
            "/api/project/phases",
            json=[{"id": "ph1", "description": "Records"}],
        )
        _seed_decision_with_phase(project_dir, phase_id="ph1")
        r = client.put(
            "/api/project/phases",
            json=[{"id": "screening", "description": "Records", "previous_id": "ph1"}],
        )
        assert r.status_code == 200
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert [d["phase_id"] for d in decisions] == ["screening"]

    def it_rejects_unknown_previous_id(self, client: TestClient):
        r = client.put(
            "/api/project/phases",
            json=[{"id": "ph1", "description": "Records", "previous_id": "ghost"}],
        )
        assert r.status_code == 400


class DescribeRenameCriterion:
    def it_propagates_id_change_to_decisions(self, client: TestClient, project_dir):
        _seed_decision(project_dir, researcher_id="alice@example.com", criterion_id="inc1")
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
