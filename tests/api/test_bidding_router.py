from fastapi.testclient import TestClient


BIB_KEY = "alpha2020systematic"
ALICE = "alice@example.com"
BOB = "bob@example.com"


class Describe_get_biddings:
    def it_returns_empty_list_initially(self, client: TestClient):
        r = client.get("/api/sets/00-start/bidding")
        assert r.status_code == 200
        assert r.json() == []

    def it_returns_404_for_unknown_set(self, client: TestClient):
        r = client.get("/api/sets/99-backward/bidding")
        assert r.status_code == 404


class Describe_add_bid:
    def it_assigns_a_work_to_researcher(self, client: TestClient, alice_headers: dict):
        r = client.put(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["researcher_id"] == ALICE
        assert BIB_KEY in body["work_ids"]

    def it_is_idempotent(self, client: TestClient, alice_headers: dict):
        client.put(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        r = client.put(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        assert r.status_code == 200
        assert r.json()["work_ids"].count(BIB_KEY) == 1

    def it_requires_researcher_header(self, client: TestClient):
        r = client.put(f"/api/sets/00-start/bidding/{BIB_KEY}")
        assert r.status_code == 401


class Describe_remove_bid:
    def it_removes_a_work_from_bidding(self, client: TestClient, alice_headers: dict):
        client.put(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        r = client.delete(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        assert r.status_code == 200
        assert BIB_KEY not in r.json()["work_ids"]

    def it_is_safe_when_work_not_bidded(self, client: TestClient, alice_headers: dict):
        r = client.delete(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        assert r.status_code == 200


class Describe_run_bidding:
    def it_assigns_works_per_percentage(self, client: TestClient):
        r = client.post("/api/bidding/run")
        assert r.status_code == 200
        summaries = r.json()
        assert any(s["set_id"] == "00-start" for s in summaries)
        start = next(s for s in summaries if s["set_id"] == "00-start")
        assert start["total_works"] == 2
        # Both researchers default to 100% → each gets 2 papers
        assert start["per_researcher"].get(ALICE) == 2
        assert start["per_researcher"].get(BOB) == 2

    def it_preserves_existing_biddings_on_rerun(self, client: TestClient, alice_headers: dict):
        client.put(f"/api/sets/00-start/bidding/{BIB_KEY}", headers=alice_headers)
        client.post("/api/bidding/run")
        r = client.get("/api/sets/00-start/bidding")
        alice_bidding = next((b for b in r.json() if b["researcher_id"] == ALICE), None)
        assert alice_bidding is not None
        assert BIB_KEY in alice_bidding["work_ids"]

    def it_returns_overlap_percentage(self, client: TestClient):
        r = client.post("/api/bidding/run")
        start = next(s for s in r.json() if s["set_id"] == "00-start")
        # 100% + 100% = 200%, all papers overlapped
        assert start["overlap_pct"] == 100.0
