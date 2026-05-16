from fastapi.testclient import TestClient


class DescribeListSets:
    def it_lists_sets_with_works(self, client: TestClient):
        r = client.get("/api/sets")
        assert r.status_code == 200
        body = r.json()
        assert [s["id"] for s in body] == ["00-start"]
        assert body[0]["iteration"] == 0
        assert body[0]["kind"] == "start"
        assert len(body[0]["works"]) == 2


class DescribeGetSet:
    def it_returns_a_specific_set(self, client: TestClient):
        r = client.get("/api/sets/00-start")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "00-start"
        assert {w["id"] for w in body["works"]} == {"sha1:7775895baced66ce", "sha1:cdc005a8929a82bf"}

    def it_returns_400_for_invalid_id(self, client: TestClient):
        r = client.get("/api/sets/garbage")
        assert r.status_code == 400

    def it_returns_404_for_missing_set(self, client: TestClient):
        r = client.get("/api/sets/01-backward")
        assert r.status_code == 404


