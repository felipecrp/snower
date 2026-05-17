from fastapi.testclient import TestClient


BIB_KEY = "alpha2020systematic"


class DescribeUpsertDecision:
    def it_creates_a_decision(self, client: TestClient, alice_headers: dict[str, str]):
        r = client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept", "criterion_id": "inc1", "note": "looks empirical"},
            headers=alice_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] == "accept"
        assert body["researcher_id"] == "alice@example.com"
        assert body["bib_key"] == BIB_KEY

    def it_replaces_previous_decision_by_same_researcher(
        self, client: TestClient, alice_headers: dict[str, str]
    ):
        client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept", "criterion_id": "inc1"},
            headers=alice_headers,
        )
        client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "reject", "criterion_id": "exc1"},
            headers=alice_headers,
        )
        r = client.get("/api/sets/00-start/decisions")
        body = r.json()
        alice_decisions = [d for d in body["decisions"] if d["researcher_id"] == "alice@example.com"]
        assert len(alice_decisions) == 1
        assert alice_decisions[0]["verdict"] == "reject"

    def it_keeps_decisions_from_other_researchers(self, client: TestClient):
        client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept"},
            headers={"X-Researcher-Id": "alice@example.com"},
        )
        client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "reject"},
            headers={"X-Researcher-Id": "bob@example.com"},
        )
        r = client.get("/api/sets/00-start/decisions")
        body = r.json()
        assert len(body["decisions"]) == 2

    def it_rejects_missing_researcher_header(self, client: TestClient):
        r = client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept"},
        )
        assert r.status_code == 401

    def it_rejects_unknown_researcher(self, client: TestClient):
        r = client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept"},
            headers={"X-Researcher-Id": "ghost"},
        )
        assert r.status_code == 403

    def it_returns_404_for_unknown_set(self, client: TestClient, alice_headers: dict[str, str]):
        r = client.put(
            f"/api/sets/99-forward/decisions/{BIB_KEY}",
            json={"verdict": "accept"},
            headers=alice_headers,
        )
        assert r.status_code == 404

    def it_persists_and_returns_phase_id(self, client: TestClient, alice_headers: dict[str, str]):
        r = client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept", "criterion_id": "inc1", "phase_id": "ph2"},
            headers=alice_headers,
        )
        assert r.status_code == 200
        assert r.json()["phase_id"] == "ph2"
        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        alice = next(d for d in decisions if d["researcher_id"] == "alice@example.com")
        assert alice["phase_id"] == "ph2"


class DescribeDeleteDecision:
    def it_removes_only_the_active_researchers_decision(
        self, client: TestClient, alice_headers: dict[str, str]
    ):
        client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "accept"},
            headers=alice_headers,
        )
        client.put(
            f"/api/sets/00-start/decisions/{BIB_KEY}",
            json={"verdict": "reject"},
            headers={"X-Researcher-Id": "bob@example.com"},
        )
        r = client.delete(f"/api/sets/00-start/decisions/{BIB_KEY}", headers=alice_headers)
        assert r.status_code == 204

        body = client.get("/api/sets/00-start/decisions").json()
        assert [d["researcher_id"] for d in body["decisions"]] == ["bob@example.com"]
