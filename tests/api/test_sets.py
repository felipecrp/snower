import io

from fastapi.testclient import TestClient

BIB_CONTENT = b"""
@article{wohlin2014,
  title = {Guidelines for Snowballing in Systematic Literature Studies},
  author = {Wohlin, Claes},
  year = {2014},
  journal = {EASE},
}

@article{kitchenham2007,
  title = {Guidelines for Performing Systematic Literature Reviews},
  author = {Kitchenham, Barbara},
  year = {2007},
  journal = {Technical Report},
}
"""


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


class DescribeParseBib:
    def it_returns_parsed_works_without_importing(self, client: TestClient):
        r = client.post(
            "/api/sets/00-start/parse-bib",
            files={"file": ("test.bib", io.BytesIO(BIB_CONTENT), "application/octet-stream")},
        )
        assert r.status_code == 200
        works = r.json()
        assert len(works) == 2
        titles = {w["title"] for w in works}
        assert "Guidelines for Snowballing in Systematic Literature Studies" in titles

    def it_does_not_change_the_set(self, client: TestClient):
        client.post(
            "/api/sets/00-start/parse-bib",
            files={"file": ("test.bib", io.BytesIO(BIB_CONTENT), "application/octet-stream")},
        )
        r = client.get("/api/sets/00-start")
        assert len(r.json()["works"]) == 2  # still only the original 2 works

    def it_returns_404_for_unknown_set(self, client: TestClient):
        r = client.post(
            "/api/sets/99-missing/parse-bib",
            files={"file": ("test.bib", io.BytesIO(BIB_CONTENT), "application/octet-stream")},
        )
        assert r.status_code == 404


class DescribeImportWork:
    def _parse_first(self, client: TestClient) -> dict:
        r = client.post(
            "/api/sets/00-start/parse-bib",
            files={"file": ("test.bib", io.BytesIO(BIB_CONTENT), "application/octet-stream")},
        )
        return r.json()[0]

    def it_imports_a_single_work_and_returns_it(self, client: TestClient):
        work = self._parse_first(client)
        r = client.post("/api/sets/00-start/import-work", json=work)
        assert r.status_code == 200
        assert r.json()["title"] == work["title"]

    def it_adds_the_work_to_the_set(self, client: TestClient):
        work = self._parse_first(client)
        client.post("/api/sets/00-start/import-work", json=work)
        r = client.get("/api/sets/00-start")
        assert len(r.json()["works"]) == 3

    def it_returns_404_for_unknown_set(self, client: TestClient):
        work = self._parse_first(client)
        r = client.post("/api/sets/99-missing/import-work", json=work)
        assert r.status_code == 404

