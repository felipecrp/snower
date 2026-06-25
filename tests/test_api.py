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
        assert data["decision_strategy"] == "majority"

    def it_updates_decision_strategy(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.patch("/", json={"decision_strategy": "consensus"})
        assert r.status_code == 200
        assert r.json()["decision_strategy"] == "consensus"


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
        assert any(s["name"] == "start_set" and s["round"] is None for s in sets)

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
        assert any(s["name"] == "start_set" for s in r.json())

    def it_lists_papers_in_set(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/sets/start_set/papers")
        assert r.status_code == 200
        papers = r.json()
        bib_ids = [p["bib_id"] for p in papers]
        assert "kitchenham2009systematic" in bib_ids
        assert papers[0]["decision"] == "undecided"


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


def _seed_review(client):
    """Seed a criterion, phase, and researcher for screening tests."""
    client.post("/criteria", json={"id": "ic1", "name": "Peer reviewed", "type": "inclusion"})
    client.post("/criteria", json={"id": "ec1", "name": "Out of scope", "type": "exclusion"})
    client.post("/phases", json={"id": "title", "name": "Title screening"})
    client.post("/researchers", json={"email": "a@b.com", "name": "Ana"})
    client.post("/researchers", json={"email": "b@b.com", "name": "Bob"})


class DescribeScreening:
    def it_records_an_inclusion_assessment_and_autosaves(self, tmp_path):
        client, project = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        r = client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ic1", "phase_id": "title", "researcher_email": "a@b.com"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["bib_id"] == "kitchenham2009systematic"
        assert body["decision"] == "included"
        assert "a@b.com" in body["assessments"]
        assert body["assessments"]["a@b.com"]["criterion"]["id"] == "ic1"

        # reload from disk to confirm autosave
        reloaded = Project.load(project.path)
        assert "a@b.com" in reloaded.assessments
        assert "kitchenham2009systematic" in reloaded.assessments["a@b.com"]

    def it_records_an_exclusion_assessment(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        r = client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ec1", "phase_id": "title", "researcher_email": "a@b.com"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["decision"] == "excluded"
        assert body["assessments"]["a@b.com"]["criterion"]["type"] == "exclusion"

    def it_returns_404_for_unknown_criterion(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        r = client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ghost", "phase_id": "title", "researcher_email": "a@b.com"},
        )
        assert r.status_code == 404

    def it_returns_404_for_unknown_phase(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        r = client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ic1", "phase_id": "ghost", "researcher_email": "a@b.com"},
        )
        assert r.status_code == 404

    def it_returns_404_for_unknown_researcher(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        r = client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ic1", "phase_id": "title", "researcher_email": "ghost@x.com"},
        )
        assert r.status_code == 404


class DescribeAssessmentsEndpoint:
    def it_returns_empty_map_before_any_assessment(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        r = client.get("/papers/kitchenham2009systematic/assessments")
        assert r.status_code == 200
        assert r.json() == {}

    def it_returns_assessments_after_screening(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ic1", "phase_id": "title", "researcher_email": "a@b.com"},
        )
        client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ec1", "phase_id": "title", "researcher_email": "b@b.com"},
        )
        r = client.get("/papers/kitchenham2009systematic/assessments")
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"a@b.com", "b@b.com"}

    def it_returns_decision_in_patch_response(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": True})
        _seed_review(client)
        r = client.patch(
            "/papers/kitchenham2009systematic",
            json={"criterion_id": "ic1", "phase_id": "title", "researcher_email": "a@b.com"},
        )
        assert r.status_code == 200
        assert r.json()["decision"] == "included"


class DescribeCriteriaEndpoints:
    def it_lists_criteria(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/criteria", json={"id": "ic1", "name": "Peer reviewed", "type": "inclusion"})
        r = client.get("/criteria")
        assert r.status_code == 200
        assert any(c["id"] == "ic1" for c in r.json())

    def it_creates_a_criterion(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.post("/criteria", json={"id": "ic1", "name": "Peer reviewed", "type": "inclusion"})
        assert r.status_code == 201

    def it_returns_409_on_duplicate_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/criteria", json={"id": "ic1", "name": "Peer reviewed", "type": "inclusion"})
        r = client.post("/criteria", json={"id": "ic1", "name": "Other", "type": "exclusion"})
        assert r.status_code == 409

    def it_updates_a_criterion(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/criteria", json={"id": "ic1", "name": "Peer reviewed", "type": "inclusion"})
        r = client.patch("/criteria/ic1", json={"id": "ic1", "name": "Updated", "type": "exclusion"})
        assert r.status_code == 204

    def it_returns_404_update_for_unknown_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.patch("/criteria/ghost", json={"id": "ghost", "name": "x", "type": "inclusion"})
        assert r.status_code == 404

    def it_deletes_a_criterion(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/criteria", json={"id": "ic1", "name": "Peer reviewed", "type": "inclusion"})
        r = client.delete("/criteria/ic1")
        assert r.status_code == 204

    def it_returns_404_delete_for_unknown_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.delete("/criteria/ghost")
        assert r.status_code == 404


class DescribePhasesEndpoints:
    def it_lists_phases(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/phases", json={"id": "title", "name": "Title screening"})
        r = client.get("/phases")
        assert r.status_code == 200
        assert any(p["id"] == "title" for p in r.json())

    def it_creates_a_phase(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.post("/phases", json={"id": "title", "name": "Title screening"})
        assert r.status_code == 201

    def it_returns_409_on_duplicate_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/phases", json={"id": "title", "name": "Title screening"})
        r = client.post("/phases", json={"id": "title", "name": "Other"})
        assert r.status_code == 409

    def it_updates_a_phase(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/phases", json={"id": "title", "name": "Title screening"})
        r = client.patch("/phases/title", json={"id": "title", "name": "Updated"})
        assert r.status_code == 204

    def it_returns_404_update_for_unknown_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.patch("/phases/ghost", json={"id": "ghost", "name": "x"})
        assert r.status_code == 404

    def it_deletes_a_phase(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/phases", json={"id": "title", "name": "Title screening"})
        r = client.delete("/phases/title")
        assert r.status_code == 204

    def it_returns_404_delete_for_unknown_id(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.delete("/phases/ghost")
        assert r.status_code == 404


class DescribeResearchersEndpoints:
    def it_lists_researchers(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/researchers", json={"email": "a@b.com", "name": "Ana"})
        r = client.get("/researchers")
        assert r.status_code == 200
        assert any(r2["email"] == "a@b.com" for r2 in r.json())

    def it_creates_a_researcher(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.post("/researchers", json={"email": "a@b.com", "name": "Ana"})
        assert r.status_code == 201

    def it_returns_409_on_duplicate_email(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/researchers", json={"email": "a@b.com", "name": "Ana"})
        r = client.post("/researchers", json={"email": "a@b.com", "name": "Other"})
        assert r.status_code == 409

    def it_updates_a_researcher(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/researchers", json={"email": "a@b.com", "name": "Ana"})
        r = client.patch("/researchers/a@b.com", json={"email": "a@b.com", "name": "Ana Updated"})
        assert r.status_code == 204

    def it_returns_404_update_for_unknown_email(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.patch("/researchers/ghost@x.com", json={"email": "ghost@x.com", "name": "x"})
        assert r.status_code == 404

    def it_deletes_a_researcher(self, tmp_path):
        client, _ = _make_client(tmp_path)
        client.post("/researchers", json={"email": "a@b.com", "name": "Ana"})
        r = client.delete("/researchers/a@b.com")
        assert r.status_code == 204

    def it_returns_404_delete_for_unknown_email(self, tmp_path):
        client, _ = _make_client(tmp_path)
        r = client.delete("/researchers/ghost@x.com")
        assert r.status_code == 404


class DescribeAddSeed:
    def it_promotes_an_existing_paper_to_seed(self, tmp_path):
        client, _ = _make_client(tmp_path)
        # import as plain paper (not a seed)
        client.post("/import", json={"bibtex": SMALL_BIBTEX, "as_seed": False})
        # not yet in start_set
        assert client.get("/sets/start_set/papers").json() == []

        r = client.post("/papers/kitchenham2009systematic/seed")
        assert r.status_code == 200
        assert "kitchenham2009systematic" in r.json()["seeds"]

        bib_ids = [p["bib_id"] for p in client.get("/sets/start_set/papers").json()]
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
