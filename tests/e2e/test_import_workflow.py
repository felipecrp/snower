"""End-to-end tests for the import and reimport feature."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.e2e.conftest import import_bib, import_work


class DescribeImportToStartSet:
    def it_creates_accept_decision_when_groups_match_include_criterion(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "00-start", "Accept Paper", groups="inc1", headers=alice)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        d = next((d for d in decisions if d["researcher_id"] == "alice@example.com"), None)
        assert d is not None
        assert d["verdict"] == "accept"
        assert d["criterion_id"] == "inc1"

    def it_creates_reject_decision_when_groups_match_exclude_criterion(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "00-start", "Reject Paper", groups="exc1", headers=alice)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        d = next((d for d in decisions if d["researcher_id"] == "alice@example.com"), None)
        assert d is not None
        assert d["verdict"] == "reject"
        assert d["criterion_id"] == "exc1"

    def it_applies_phase_when_groups_include_a_phase_id(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "00-start", "Phase Paper", groups="inc1,ph1", headers=alice)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        d = next((d for d in decisions if d["researcher_id"] == "alice@example.com"), None)
        assert d is not None
        assert d["verdict"] == "accept"
        assert d["phase_id"] == "ph1"

    def it_does_not_create_a_decision_without_an_active_researcher(
        self, client: TestClient
    ):
        import_work(client, "00-start", "No Researcher Paper", groups="inc1")

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        assert decisions == []


class DescribeImportToOrphan:
    def it_stages_an_unplaced_work_in_the_orphan_set(self, client: TestClient):
        import_work(client, "orphan", "Orphan Paper")

        sets = {s["id"]: s for s in client.get("/api/sets").json()}
        assert "orphan" in sets
        orphan_titles = {w["title"] for w in sets["orphan"]["works"]}
        assert "Orphan Paper" in orphan_titles

        regular_titles = {
            w["title"]
            for sid, s in sets.items()
            if sid != "orphan"
            for w in s["works"]
        }
        assert "Orphan Paper" not in regular_titles

    def it_applies_group_decision_to_the_orphan_work(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "orphan", "Orphan Reject", groups="exc1", headers=alice)

        sets = {s["id"]: s for s in client.get("/api/sets").json()}
        orphan_work = next(
            w for w in sets["orphan"]["works"] if w["title"] == "Orphan Reject"
        )
        decisions = client.get("/api/sets/orphan/decisions").json()["decisions"]
        d = next(
            (d for d in decisions
             if d["bib_id"] == orphan_work["bib_key"]
             and d["researcher_id"] == "alice@example.com"),
            None,
        )
        assert d is not None
        assert d["verdict"] == "reject"
        assert d["criterion_id"] == "exc1"


class DescribeReimport:
    def it_flips_verdict_when_reimported_with_a_different_criterion_group(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "00-start", "Flip Paper", year=2021, groups="inc1", headers=alice)
        import_work(client, "00-start", "Flip Paper", year=2021, groups="exc1", headers=alice)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        alice_decisions = [d for d in decisions if d["researcher_id"] == "alice@example.com"]
        assert len(alice_decisions) == 1
        assert alice_decisions[0]["verdict"] == "reject"
        assert alice_decisions[0]["criterion_id"] == "exc1"

    def it_updates_phase_when_reimported_with_a_different_phase_group(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "00-start", "Phase Paper", year=2022, groups="inc1,ph1", headers=alice)
        import_work(client, "00-start", "Phase Paper", year=2022, groups="inc1,ph2", headers=alice)

        decisions = client.get("/api/sets/00-start/decisions").json()["decisions"]
        d = next(
            (d for d in decisions if d["researcher_id"] == "alice@example.com"), None
        )
        assert d is not None
        assert d["phase_id"] == "ph2"

    def it_fills_missing_metadata_but_keeps_existing_values(
        self, client: TestClient, alice: dict
    ):
        bib_first = """\
@article{meta2020,
  title  = {Metadata Paper},
  author = {Author, A},
  year   = {2020},
  journal = {Original Venue},
}
"""
        bib_second = """\
@article{meta2020,
  title   = {Metadata Paper},
  author  = {Author, A},
  year    = {2020},
  journal = {Different Venue},
  doi     = {10.9999/test},
}
"""
        import_bib(client, "00-start", bib_first, headers=alice)
        import_bib(client, "00-start", bib_second, headers=alice)

        works = client.get("/api/sets/00-start").json()["works"]
        w = next(w for w in works if w["title"] == "Metadata Paper")
        assert w["venue"] == "Original Venue"
        assert w["doi"] == "10.9999/test"

    def it_does_not_duplicate_a_work_on_reimport(
        self, client: TestClient, alice: dict
    ):
        import_work(client, "00-start", "Unique Paper", year=2023, groups="inc1", headers=alice)
        import_work(client, "00-start", "Unique Paper", year=2023, groups="inc1", headers=alice)

        works = client.get("/api/sets/00-start").json()["works"]
        matching = [w for w in works if w["title"] == "Unique Paper"]
        assert len(matching) == 1
