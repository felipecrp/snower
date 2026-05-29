"""End-to-end tests for the orphan set lifecycle — features 7.1–7.3."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from snow.domain.models import BibliographicWork
from tests.e2e.conftest import decide, import_work, mock_provider


def _run_backward(client: TestClient, references: list[BibliographicWork]) -> None:
    provider = mock_provider(references=references)
    with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
        r = client.post("/api/snowballing/backward")
    assert r.status_code == 200


class DescribeOrphanEviction:
    def it_moves_backward_papers_to_orphan_when_source_is_rejected(
        self, client: TestClient, alice: dict
    ):
        source_key = import_work(client, "00-start", "Source Paper")
        decide(client, "00-start", source_key, "accept", "inc1", alice)

        _run_backward(client, [
            BibliographicWork(title="Backward Child", authors=("C, C",), year=2010),
        ])
        backward_set = client.get("/api/sets/01-backward").json()
        assert len(backward_set["works"]) == 1

        # Reject the source → child becomes disconnected
        decide(client, "00-start", source_key, "reject", "exc1", alice)
        r = client.post("/api/orphans/recalculate")
        assert r.status_code == 200

        orphan_set = next((s for s in r.json() if s["id"] == "orphan"), None)
        assert orphan_set is not None
        orphan_titles = {w["title"] for w in orphan_set["works"]}
        assert "Backward Child" in orphan_titles

        backward = next((s for s in r.json() if s["id"] == "01-backward"), None)
        if backward:
            backward_titles = {w["title"] for w in backward["works"]}
            assert "Backward Child" not in backward_titles

    def it_does_not_orphan_papers_that_remain_connected(
        self, client: TestClient, alice: dict, bob: dict
    ):
        key_a = import_work(client, "00-start", "Source Stays Accepted")
        key_b = import_work(client, "00-start", "Source To Reject")
        decide(client, "00-start", key_a, "accept", "inc1", alice)
        decide(client, "00-start", key_b, "accept", "inc1", alice)

        _run_backward(client, [
            BibliographicWork(title="Child Of A", authors=("A, A",), year=2010),
        ])
        # key_b also accepted but has no children in this run

        # Reject key_b — only its children (none) should orphan; key_a's child stays
        decide(client, "00-start", key_b, "reject", "exc1", alice)
        r = client.post("/api/orphans/recalculate")

        sets = {s["id"]: s for s in r.json()}
        orphan_titles = {w["title"] for w in sets.get("orphan", {}).get("works", [])}
        assert "Child Of A" not in orphan_titles


class DescribeOrphanReturn:
    def it_returns_orphan_to_iteration_set_when_source_re_accepted(
        self, client: TestClient, alice: dict
    ):
        source_key = import_work(client, "00-start", "Re-accepted Source")
        decide(client, "00-start", source_key, "accept", "inc1", alice)

        _run_backward(client, [
            BibliographicWork(title="Returning Child", authors=("R, R",), year=2012),
        ])

        # Reject → orphan
        decide(client, "00-start", source_key, "reject", "exc1", alice)
        client.post("/api/orphans/recalculate")

        sets_after_reject = {s["id"]: s for s in client.get("/api/sets").json()}
        orphan_titles = {w["title"] for w in sets_after_reject.get("orphan", {}).get("works", [])}
        assert "Returning Child" in orphan_titles

        # Re-accept → child should return to 01-backward
        decide(client, "00-start", source_key, "accept", "inc1", alice)
        r = client.post("/api/orphans/recalculate")

        sets_after_accept = {s["id"]: s for s in r.json()}
        backward_titles = {w["title"] for w in sets_after_accept.get("01-backward", {}).get("works", [])}
        orphan_titles_after = {w["title"] for w in sets_after_accept.get("orphan", {}).get("works", [])}
        assert "Returning Child" in backward_titles
        assert "Returning Child" not in orphan_titles_after


class DescribeManualRecalculation:
    def it_is_idempotent_when_nothing_changed(
        self, client: TestClient, alice: dict
    ):
        source_key = import_work(client, "00-start", "Stable Source")
        decide(client, "00-start", source_key, "accept", "inc1", alice)

        _run_backward(client, [
            BibliographicWork(title="Stable Child", authors=("S, S",), year=2011),
        ])

        r1 = client.post("/api/orphans/recalculate")
        r2 = client.post("/api/orphans/recalculate")
        assert r1.status_code == 200
        assert r2.status_code == 200

        sets1 = {s["id"]: [w["title"] for w in s["works"]] for s in r1.json()}
        sets2 = {s["id"]: [w["title"] for w in s["works"]] for s in r2.json()}
        assert sets1 == sets2
