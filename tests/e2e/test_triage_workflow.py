"""End-to-end tests for the triage (decision) lifecycle — features 5.1–5.5."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.e2e.conftest import decide, import_work


class DescribeTriageWorkflow:
    def it_records_independent_decisions_per_researcher(
        self, client: TestClient, alice: dict, bob: dict
    ):
        bib_key = import_work(client, "00-start", "Survey on Snowballing")

        decide(client, "00-start", bib_key, "accept", "inc1", alice)
        decide(client, "00-start", bib_key, "reject", "exc1", bob)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        alice_d = next(d for d in decisions if d["researcher_id"] == "alice@example.com")
        bob_d = next(d for d in decisions if d["researcher_id"] == "bob@example.com")
        assert alice_d["verdict"] == "accept"
        assert bob_d["verdict"] == "reject"

    def it_overwrites_previous_decision_from_same_researcher(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Survey on Snowballing")

        decide(client, "00-start", bib_key, "accept", "inc1", alice)
        decide(client, "00-start", bib_key, "reject", "exc1", alice)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        alice_decisions = [d for d in decisions if d["researcher_id"] == "alice@example.com"]
        assert len(alice_decisions) == 1
        assert alice_decisions[0]["verdict"] == "reject"

    def it_deletes_only_the_requesting_researchers_decision(
        self, client: TestClient, alice: dict, bob: dict
    ):
        bib_key = import_work(client, "00-start", "Paper To Partially Undo")

        decide(client, "00-start", bib_key, "accept", "inc1", alice)
        decide(client, "00-start", bib_key, "reject", "exc1", bob)

        r = client.delete(f"/api/sets/00-start/decisions/{bib_key}", headers=alice)
        assert r.status_code == 204

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        remaining = [d["researcher_id"] for d in decisions]
        assert "alice@example.com" not in remaining
        assert "bob@example.com" in remaining

    def it_persists_phase_and_note_through_full_cycle(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Phase Annotated Paper")

        r = client.put(
            f"/api/sets/00-start/decisions/{bib_key}",
            json={"verdict": "accept", "criterion_id": "inc1", "phase_id": "ph1", "note": "important"},
            headers=alice,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["phase_id"] == "ph1"
        assert body["note"] == "important"

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        saved = next(d for d in decisions if d["researcher_id"] == "alice@example.com")
        assert saved["phase_id"] == "ph1"
        assert saved["note"] == "important"

    def it_applies_decisions_across_multiple_papers(
        self, client: TestClient, alice: dict, bob: dict
    ):
        key_a = import_work(client, "00-start", "Paper Alpha", year=2020)
        key_b = import_work(client, "00-start", "Paper Beta", year=2021)

        decide(client, "00-start", key_a, "accept", "inc1", alice)
        decide(client, "00-start", key_a, "accept", "inc1", bob)
        decide(client, "00-start", key_b, "reject", "exc1", alice)
        decide(client, "00-start", key_b, "reject", "exc1", bob)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        alpha_decisions = [d for d in decisions if d["bib_id"] == key_a]
        beta_decisions = [d for d in decisions if d["bib_id"] == key_b]
        assert all(d["verdict"] == "accept" for d in alpha_decisions)
        assert all(d["verdict"] == "reject" for d in beta_decisions)
