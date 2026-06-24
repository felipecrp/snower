from fastapi.testclient import TestClient

from snower.api.app import app
from snower.api.project import get_project
from snower.project import Project

SMALL_BIBTEX = """
@article{kitchenham2009systematic,
  author = {Kitchenham, Barbara},
  title = {Systematic literature reviews in software engineering},
  year = {2009},
  journal = {IST},
}
"""

NO_BIB_ID_BIBTEX = """
@article{noname,
  title = {A paper without author or year},
}
"""


def _make_client(tmp_path):
    """Return a TestClient backed by a fresh in-memory project at tmp_path."""
    project = Project(name="test", path=tmp_path / "test")
    app.dependency_overrides[get_project] = lambda: project
    return TestClient(app), project


class DescribeProjectSummary:
    def it_returns_project_summary(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "test"
        assert data["seeds"] == []
        assert data["sets"] == []


class DescribeImport:
    def it_imports_a_paper_as_seed(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        assert r.status_code == 200
        body = r.json()
        assert "kitchenham2009systematic" in body["imported"]
        assert body["skipped"] == []

    def it_places_seed_in_start_0(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/sets")
        sets = r.json()
        assert any(s["name"] == "start" and s["round"] == 0 for s in sets)

    def it_skips_papers_without_bib_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.post("/import", json={"bibtex": NO_BIB_ID_BIBTEX, "as_seed": False})
        assert r.status_code == 200
        body = r.json()
        assert body["imported"] == []
        assert len(body["skipped"]) == 1


class DescribeSets:
    def it_lists_sets_after_import(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/sets")
        assert r.status_code == 200
        assert any(s["name"] == "start" for s in r.json())

    def it_lists_papers_in_set(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/sets/start-0/papers")
        assert r.status_code == 200
        bib_ids = [p["bib_id"] for p in r.json()]
        assert "kitchenham2009systematic" in bib_ids


class DescribePapers:
    def it_lists_all_papers(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/papers")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def it_gets_a_single_paper(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/papers/kitchenham2009systematic")
        assert r.status_code == 200
        assert r.json()["bib_id"] == "kitchenham2009systematic"

    def it_returns_404_for_unknown_paper(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.get("/papers/ghost")
        assert r.status_code == 404


class DescribeScreening:
    def it_excludes_a_paper_and_autosaves(self, tmp_path):
        client, project = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.patch("/papers/kitchenham2009systematic", json={"included": False})
        assert r.status_code == 200
        assert r.json()["included"] is False

        # reload from disk to confirm autosave
        reloaded = Project.load(project.path)
        assert reloaded.papers["kitchenham2009systematic"].included is False

    def it_reincluded_a_paper(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        client.patch("/papers/kitchenham2009systematic", json={"included": False})
        r = client.patch("/papers/kitchenham2009systematic", json={"included": True})
        assert r.status_code == 200
        assert r.json()["included"] is True


class DescribeAddSeed:
    def it_promotes_an_existing_paper_to_seed(self, tmp_path):
        client, _ = _make_client(tmp_path)
        # import as plain paper (not a seed)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": False})
        # not yet in start-0
        assert client.get("/sets/start-0/papers").json() == []

        r = client.post("/papers/kitchenham2009systematic/seed")
        assert r.status_code == 200
        assert "kitchenham2009systematic" in r.json()["seeds"]

        bib_ids = [p["bib_id"] for p in client.get("/sets/start-0/papers").json()]
        assert "kitchenham2009systematic" in bib_ids

    def it_returns_404_for_unknown_bib_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.post("/papers/ghost/seed")
        assert r.status_code == 404


class DescribeRemoveSeed:
    def it_removes_a_seed(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})

        r = client.delete("/papers/kitchenham2009systematic/seed")
        assert r.status_code == 200
        assert "kitchenham2009systematic" not in r.json()["seeds"]

    def it_returns_404_when_paper_is_not_a_seed(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": False})
        r = client.delete("/papers/kitchenham2009systematic/seed")
        assert r.status_code == 404

    def it_returns_404_for_unknown_bib_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.delete("/papers/ghost/seed")
        assert r.status_code == 404
