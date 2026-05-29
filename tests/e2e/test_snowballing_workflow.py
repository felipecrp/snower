"""End-to-end tests for the snowballing lifecycle — features 6.1–6.5."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from snow.domain.models import BibliographicWork
from tests.e2e.conftest import decide, import_work, mock_provider


class DescribeBackwardSnowballing:
    def it_creates_an_iteration_set_from_accepted_papers(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Snowballing Guidelines")
        decide(client, "00-start", bib_key, "accept", "inc1", alice)

        references = [
            BibliographicWork(title="Reference A", authors=("Alpha, A",), year=2015),
            BibliographicWork(title="Reference B", authors=("Beta, B",), year=2016),
        ]
        provider = mock_provider(references=references)

        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            r = client.post("/api/snowballing/backward")

        assert r.status_code == 200
        created_sets = r.json()
        set_ids = [s["id"] for s in created_sets]
        assert "01-backward" in set_ids

        backward_set = next(s for s in created_sets if s["id"] == "01-backward")
        titles = {w["title"] for w in backward_set["works"]}
        assert "Reference A" in titles
        assert "Reference B" in titles

    def it_places_results_in_the_correct_iteration_number(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Iteration Source Paper")
        decide(client, "00-start", bib_key, "accept", "inc1", alice)

        provider = mock_provider(
            references=[BibliographicWork(title="Child Ref", authors=("C, C",), year=2010)]
        )
        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            r = client.post("/api/snowballing/backward")

        sets = client.get("/api/sets").json()
        backward = next(s for s in sets if s["id"] == "01-backward")
        assert backward["iteration"] == 1
        assert backward["kind"] == "backward"

    def it_skips_papers_already_snowballed(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Already Snowballed Paper")
        decide(client, "00-start", bib_key, "accept", "inc1", alice)

        provider = mock_provider(
            references=[BibliographicWork(title="Child", authors=("D, D",), year=2012)]
        )
        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            client.post("/api/snowballing/backward")
            # Second call — paper already logged as done
            r = client.post("/api/snowballing/backward")

        assert r.status_code == 200
        # Provider fetch should only be called once across both runs
        assert provider.fetch_references.call_count == 1

    def it_forces_a_rerun_when_force_is_true(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Force Rerun Paper")
        decide(client, "00-start", bib_key, "accept", "inc1", alice)

        provider = mock_provider(
            references=[BibliographicWork(title="Force Child", authors=("E, E",), year=2013)]
        )
        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            client.post("/api/snowballing/backward")
            r = client.post("/api/snowballing/backward?force=true")

        assert r.status_code == 200
        assert provider.fetch_references.call_count == 2

    def it_returns_empty_when_no_accepted_papers(self, client: TestClient):
        provider = mock_provider()
        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            r = client.post("/api/snowballing/backward")

        assert r.status_code == 200
        assert r.json() == []
        provider.fetch_references.assert_not_called()


class DescribeForwardSnowballing:
    def it_creates_a_forward_iteration_set(
        self, client: TestClient, alice: dict
    ):
        bib_key = import_work(client, "00-start", "Cited By Others Paper")
        decide(client, "00-start", bib_key, "accept", "inc1", alice)

        citations = [
            BibliographicWork(title="Citing Paper X", authors=("X, X",), year=2022),
        ]
        provider = mock_provider(citations=citations)

        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            r = client.post("/api/snowballing/forward")

        assert r.status_code == 200
        set_ids = [s["id"] for s in r.json()]
        assert "01-forward" in set_ids


class DescribePerPaperSnowballing:
    def it_snowballs_only_the_specified_paper(
        self, client: TestClient, alice: dict
    ):
        key_a = import_work(client, "00-start", "Paper Snowball Only A", year=2020)
        key_b = import_work(client, "00-start", "Paper Snowball Skip B", year=2021)
        decide(client, "00-start", key_a, "accept", "inc1", alice)
        decide(client, "00-start", key_b, "accept", "inc1", alice)

        provider = mock_provider(
            references=[BibliographicWork(title="Ref For A Only", authors=("R, R",), year=2010)]
        )
        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            r = client.post(f"/api/snowballing/backward/{key_a}")

        assert r.status_code == 200
        # Provider called once, only for key_a
        assert provider.fetch_references.call_count == 1
        called_work = provider.fetch_references.call_args[0][0]
        assert called_work.bib_key == key_a

    def it_returns_404_for_unknown_bib_key(self, client: TestClient):
        provider = mock_provider()
        with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
            r = client.post("/api/snowballing/backward/nonexistent-key")
        assert r.status_code == 404
