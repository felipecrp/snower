from datetime import datetime
from pathlib import Path

import pytest

from snow.domain.identity import BibliographicWork
from snow.domain.models import (
    Criterion,
    CriterionKind,
    Decision,
    Project,
    Relation,
    Researcher,
    Resolution,
    Set as ReviewSet,
    SetKind,
    Verdict,
    Work,
)
from snow.storage.repo import ProjectRepo


class FakeProvider:
    def __init__(self, refs=None, cites=None):
        self.refs = refs or {}
        self.cites = cites or {}

    def fetch_references(self, work):
        return self.refs.get(work.id, [])

    def fetch_citations(self, work):
        return self.cites.get(work.id, [])


def _decision(work_id, researcher_id, verdict):
    return Decision(
        work_id=work_id,
        researcher_id=researcher_id,
        verdict=verdict,
        decided_at=datetime(2026, 1, 1),
    )


def _ref(title, doi=None, venue=None, url=None, pdf_url=None, abstract=None):
    return BibliographicWork(
        title=title,
        year=2020,
        authors=("Doe, J",),
        doi=doi,
        venue=venue,
        url=url,
        pdf_url=pdf_url,
        abstract=abstract,
    )


@pytest.fixture
def project() -> Project:
    return Project(
        name="demo",
        description="snowballing demo",
        researchers=[Researcher(id="r1", name="Alice", email="alice@example.com")],
        criteria=[Criterion(id="c1", kind=CriterionKind.INCLUDE, description="empirical study")],
    )


@pytest.fixture
def sample_works() -> list[Work]:
    return [
        Work(id="sha1:7775895baced66ce", bib_key="a2020", title="A", authors=["A, A"], year=2020, doi="10/a"),
        Work(id="sha1:cdc005a8929a82bf", bib_key="b2021", title="B", authors=["B, B"], year=2021, doi="10/b"),
    ]


class DescribeProjectRepoInit:
    def it_creates_project_yml_and_sets_dir(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        assert (tmp_path / "proj" / "project.yml").exists()
        assert (tmp_path / "proj" / "sets").is_dir()
        assert (tmp_path / "proj" / "relations.yml").exists()

    def it_round_trips_project(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        loaded = repo.load_project()
        assert loaded.name == project.name
        assert loaded.researchers == project.researchers
        assert loaded.criteria == project.criteria


class DescribeProjectRepoSets:
    def it_imports_start_set(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        start = repo.import_start_set(sample_works)
        assert start.id == "00-start"
        assert start.kind == SetKind.START
        assert start.iteration == 0
        assert (tmp_path / "proj" / "sets" / "00-start" / "set.yml").exists()
        for w in start.works:
            assert (tmp_path / "proj" / "works" / f"{w.bib_key}.bib").exists()

    def it_lists_set_ids_sorted(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        (repo.sets_dir() / "01-backward").mkdir()
        (repo.sets_dir() / "ignored-dir").mkdir()
        assert repo.list_set_ids() == ["00-start", "01-backward"]

    def it_round_trips_a_set(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        loaded = repo.load_set("00-start")
        assert loaded.iteration == 0
        assert loaded.kind == SetKind.START
        assert {w.id for w in loaded.works} == {"sha1:7775895baced66ce", "sha1:cdc005a8929a82bf"}

    def it_recomputes_ids_after_import_enrichment(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        work = Work(id="sha1:old", bib_key="a2020", title="A", authors=["A, A"], year=2020, doi="10/a")

        repo.import_start_set([work])

        loaded = repo.load_set("00-start")
        assert loaded.works[0].id == "sha1:7775895baced66ce"

    def it_merges_reimported_enriched_metadata_without_duplicating(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        original = Work(
            id="sha1:15bd402faa106b69",
            bib_key="a2020",
            title="A",
            authors=["A, A"],
            year=2020,
        )
        repo.import_start_set([original])
        original_id = repo.load_set("00-start").works[0].id
        repo.save_decisions("00-start", [_decision(original_id, "r1", Verdict.ACCEPT)])
        enriched = Work(
            id=original_id,
            bib_key="a2020",
            title="A",
            authors=["A, A"],
            year=2020,
            doi="10/a",
            url="https://example.com/a",
            abstract="Abstract from OpenAlex",
        )

        updated = repo.import_bib_to_set("00-start", [enriched])

        assert len(updated.works) == 1
        assert updated.works[0].id == "sha1:7775895baced66ce"
        assert updated.works[0].doi == "10/a"
        assert updated.works[0].url == "https://example.com/a"
        assert updated.works[0].abstract == "Abstract from OpenAlex"
        decisions, _ = repo.load_decisions("00-start")
        assert decisions[0].work_id == "sha1:7775895baced66ce"

    def it_rejects_invalid_set_id(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        with pytest.raises(ValueError):
            repo.load_set("nonsense")


class DescribeProjectRepoDecisions:
    def it_round_trips_decisions_and_resolutions(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.save_set(repo.import_start_set([]))
        decisions = [
            Decision(
                work_id="sha1:7775895baced66ce",
                researcher_id="r1",
                verdict=Verdict.ACCEPT,
                criterion_id="c1",
                decided_at=datetime(2026, 5, 15, 12, 0, 0),
            )
        ]
        resolutions = [
            Resolution(
                work_id="sha1:7775895baced66ce",
                verdict=Verdict.ACCEPT,
                by="vote",
                resolved_at=datetime(2026, 5, 16, 9, 0, 0),
            )
        ]
        repo.save_decisions("00-start", decisions, resolutions)
        loaded_d, loaded_r = repo.load_decisions("00-start")
        assert loaded_d == decisions
        assert loaded_r == resolutions

    def it_returns_empty_when_no_decisions_file(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set([])
        d, r = repo.load_decisions("00-start")
        assert d == [] and r == []


class DescribeProjectRepoKeyMinting:
    def it_renames_imported_keys_to_surname_year_slug(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(
                id="sha1:placeholder",
                bib_key="garbageId123",
                title="Snowballing in systematic literature reviews",
                authors=["Wohlin, Claus"],
                year=2014,
                doi="10/wohlin",
            )
        ]
        start = repo.import_start_set(works)
        assert start.works[0].bib_key == "wohlin2014snowballingsystematic"
        # The stored work_id is the canonical sha1 of (surname|year|title),
        # whatever was passed in import_start_set is overwritten.
        keys = repo.load_keys()
        assert list(keys.keys()) == ["wohlin2014snowballingsystematic"]
        assert keys["wohlin2014snowballingsystematic"] == start.works[0].id

    def it_disambiguates_with_hash_when_slug_collides(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(id="sha1:23440077d4c90157", bib_key="x",
                 title="Snowballing studies version one",
                 authors=["Wohlin, Claus"], year=2014, doi="10/a"),
            Work(id="sha1:a30b2382d7a2ea0f", bib_key="y",
                 title="Snowballing studies version two",
                 authors=["Wohlin, Claus"], year=2014, doi="10/b"),
        ]
        start = repo.import_start_set(works)
        first, second = (w.bib_key for w in start.works)
        assert first == "wohlin2014snowballingstudies"
        assert second.startswith("wohlin2014snowballingstudies_")
        assert len(second.split("_")[-1]) == 4

    def it_reuses_existing_key_when_work_id_already_known(
        self, tmp_path: Path, project: Project
    ):
        from snow.domain.identity import WorkRef, work_id
        from snow.domain.models import Set as ReviewSet
        from snow.domain.models import SetKind as Kind

        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(
            [Work(id="sha1:placeholder", bib_key="x",
                  title="Snowballing systematic review",
                  authors=["Wohlin, Claus"], year=2014, doi="10/a")]
        )
        # Use the same canonical work_id so the reuse path triggers.
        same_id = work_id(WorkRef(title="Snowballing systematic review",
                                  authors=("Wohlin, Claus",), year=2014))
        new_set = ReviewSet(
            id="01-backward",
            kind=Kind.BACKWARD,
            iteration=1,
            works=[
                Work(id=same_id, bib_key="reimported",
                     title="Snowballing systematic review",
                     authors=["Wohlin"], year=2014, doi="10/a"),
                Work(id="sha1:other-placeholder", bib_key="other",
                     title="Guidelines for empirical research",
                     authors=["Wohlin, Claus"], year=2014, doi="10/b"),
            ],
        )
        repo.save_set(new_set)
        assert new_set.works[0].bib_key == "wohlin2014snowballingsystematic"
        assert new_set.works[1].bib_key == "wohlin2014guidelinesempirical"

    def it_persists_keys_yml_sorted(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(
            [
                Work(id="sha1:1f3edef7e27228c2", bib_key="zz",
                     title="Snowballing literature review",
                     authors=["Zeta, Z"], year=2020, doi="10/z"),
                Work(id="sha1:7775895baced66ce", bib_key="aa",
                     title="Snowballing literature review",
                     authors=["Alpha, A"], year=2020, doi="10/a"),
            ]
        )
        text = (tmp_path / "proj" / "keys.yml").read_text()
        assert text.index("alpha2020") < text.index("zeta2020")


class DescribeWorksLibrary:
    def it_stores_each_paper_once_across_sets(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        w = Work(
            id="sha1:7775895baced66ce",
            bib_key="",
            title="Shared Paper",
            authors=["Doe, J"],
            year=2020,
            doi="10/shared",
        )
        start = repo.import_start_set([w])
        canonical = start.works[0]
        repo.save_set(ReviewSet(
            id="01-backward", kind=SetKind.BACKWARD, iteration=1, works=[canonical],
        ))

        bib_files = list((tmp_path / "proj" / "works").glob("*.bib"))
        assert len(bib_files) == 1
        assert canonical.bib_key in (tmp_path / "proj" / "sets" / "00-start" / "set.yml").read_text()
        assert canonical.bib_key in (tmp_path / "proj" / "sets" / "01-backward" / "set.yml").read_text()

    def it_propagates_enrichment_to_all_sets_via_shared_file(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        bare = Work(id="sha1:placeholder", bib_key="", title="P", authors=["A, A"], year=2020)
        start = repo.import_start_set([bare])
        repo.save_set(ReviewSet(
            id="01-backward", kind=SetKind.BACKWARD, iteration=1, works=[start.works[0]],
        ))

        enriched = start.works[0].model_copy(update={
            "abstract": "Filled by OpenAlex",
            "doi": "10/p",
        })
        repo.save_work(enriched)

        for sid in ("00-start", "01-backward"):
            reloaded = repo.load_set(sid)
            assert reloaded.works[0].abstract == "Filled by OpenAlex"
            assert reloaded.works[0].doi == "10/p"

    def it_merges_with_library_fills_only_gaps(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        cached = Work(
            id="sha1:7775895baced66ce",
            bib_key="",
            title="P",
            authors=["Doe, J"],
            year=2020,
            doi="10/p",
            abstract="Cached abstract",
        )
        repo.import_start_set([cached])

        incoming = Work(
            id="sha1:7775895baced66ce",
            bib_key="garbage",
            title="P",
            authors=["Doe, J"],
            year=2020,
            url="https://example.com/p",
        )

        merged = repo.merge_with_library([incoming])

        assert merged[0].abstract == "Cached abstract"
        assert merged[0].doi == "10/p"
        assert merged[0].url == "https://example.com/p"


class DescribeRecalculateOrphans:
    def _setup_two_sets(self, repo):
        accepted = Work(id="sha1:41eaadf616eef77b", bib_key="", title="Accepted",
                        authors=["A, A"], year=2020, doi="10/a")
        ref = Work(id="sha1:bca4065a2d0d87ea", bib_key="", title="Ref",
                   authors=["B, B"], year=2021, doi="10/b")
        repo.save_set(ReviewSet(id="00-start", kind=SetKind.START, iteration=0, works=[accepted]))
        repo.save_set(ReviewSet(id="01-backward", kind=SetKind.BACKWARD, iteration=1, works=[ref]))
        accepted_persisted = repo.load_set("00-start").works[0]
        ref_persisted = repo.load_set("01-backward").works[0]
        repo.save_relations([Relation(
            citing_bib_key=accepted_persisted.bib_key,
            cited_bib_key=ref_persisted.bib_key,
        )])
        return accepted_persisted, ref_persisted

    def it_moves_disconnected_backward_works_to_orphan_set(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        accepted, ref = self._setup_two_sets(repo)
        repo.save_decisions("00-start", [_decision(accepted.id, "r1", Verdict.ACCEPT)])

        # First: ref is connected → stays in 01-backward.
        repo.recalculate_orphans()
        assert len(repo.load_set("01-backward").works) == 1

        # Reject → ref becomes orphan.
        repo.save_decisions("00-start", [_decision(accepted.id, "r1", Verdict.REJECT)])
        repo.recalculate_orphans()

        assert len(repo.load_set("01-backward").works) == 0
        assert {w.id for w in repo.load_set("orphan").works} == {ref.id}

    def it_returns_orphan_to_earliest_valid_iteration_set_when_reconnected(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        accepted, ref = self._setup_two_sets(repo)

        # Reject → ref becomes orphan.
        repo.save_decisions("00-start", [_decision(accepted.id, "r1", Verdict.REJECT)])
        repo.recalculate_orphans()
        assert {w.id for w in repo.load_set("orphan").works} == {ref.id}

        # Re-accept → ref returns to 01-backward.
        repo.save_decisions("00-start", [_decision(accepted.id, "r1", Verdict.ACCEPT)])
        repo.recalculate_orphans()

        assert repo.load_set("orphan").works == []
        assert {w.id for w in repo.load_set("01-backward").works} == {ref.id}


class DescribeProjectRepoRelations:
    def it_round_trips_relations(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        rels = [Relation(citing_bib_key="wohlin2014a", cited_bib_key="wohlin2014b")]
        repo.save_relations(rels)
        assert repo.load_relations() == rels

    def it_starts_empty(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        assert repo.load_relations() == []


class DescribeRunGlobalSnowballing:
    def it_creates_backward_set_from_accepted_start_papers(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        repo.save_decisions("00-start", [_decision("sha1:7775895baced66ce", "r1", Verdict.ACCEPT)])
        provider = FakeProvider(refs={"sha1:7775895baced66ce": [_ref("Ref Paper", doi="10/ref")]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert len(updated) == 1
        assert updated[0].id == "01-backward"
        assert updated[0].iteration == 1
        assert len(updated[0].works) == 1
        assert updated[0].works[0].title == "Ref Paper"

    def it_populates_metadata_from_provider_refs(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        repo.save_decisions("00-start", [_decision("sha1:7775895baced66ce", "r1", Verdict.ACCEPT)])
        provider = FakeProvider(refs={
            "sha1:7775895baced66ce": [
                _ref(
                    "Ref Paper",
                    doi="10/ref",
                    venue="Journal of Examples",
                    url="https://example.com/ref",
                    pdf_url="https://example.com/ref.pdf",
                    abstract="Provider abstract",
                ),
            ],
        })

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        work = updated[0].works[0]
        assert work.doi == "10/ref"
        assert work.venue == "Journal of Examples"
        assert work.url == "https://example.com/ref"
        assert work.pdf_url == "https://example.com/ref.pdf"
        assert work.abstract == "Provider abstract"

    def it_creates_forward_set_from_accepted_start_papers(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        repo.save_decisions("00-start", [_decision("sha1:7775895baced66ce", "r1", Verdict.ACCEPT)])
        provider = FakeProvider(cites={"sha1:7775895baced66ce": [_ref("Citing Paper", doi="10/cite")]})

        updated = repo.run_global_snowballing(SetKind.FORWARD, provider)

        assert len(updated) == 1
        assert updated[0].id == "01-forward"

    def it_skips_papers_rejected_by_majority(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        # Tie (1 accept, 1 reject) → not accepted
        repo.save_decisions("00-start", [
            _decision("sha1:7775895baced66ce", "r1", Verdict.ACCEPT),
            _decision("sha1:7775895baced66ce", "r2", Verdict.REJECT),
        ])
        provider = FakeProvider(refs={"sha1:7775895baced66ce": [_ref("Should Not Appear")]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert updated == []

    def it_skips_papers_with_no_decisions(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        provider = FakeProvider(refs={"sha1:7775895baced66ce": [_ref("Should Not Appear")]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert updated == []

    def it_merges_papers_from_same_iteration_into_one_target_set(
        self, tmp_path: Path, project: Project
    ):
        """Papers from backward-1 and forward-1 (both iteration=1) feed into backward-2."""
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)

        paper_bwd = Work(id="sha1:fa1bf5c7d1fe99e7", bib_key="", title="BWD", authors=["A, A"], year=2020, doi="10/bwd")
        paper_fwd = Work(id="sha1:5ca6c7f2333cc463", bib_key="", title="FWD", authors=["B, B"], year=2021, doi="10/fwd")
        repo.save_set(ReviewSet(id="01-backward", kind=SetKind.BACKWARD, iteration=1, works=[paper_bwd]))
        repo.save_set(ReviewSet(id="01-forward", kind=SetKind.FORWARD, iteration=1, works=[paper_fwd]))
        repo.save_decisions("01-backward", [_decision("sha1:fa1bf5c7d1fe99e7", "r1", Verdict.ACCEPT)])
        repo.save_decisions("01-forward", [_decision("sha1:5ca6c7f2333cc463", "r1", Verdict.ACCEPT)])

        provider = FakeProvider(refs={
            "sha1:fa1bf5c7d1fe99e7": [_ref("Ref from BWD", doi="10/rbwd")],
            "sha1:5ca6c7f2333cc463": [_ref("Ref from FWD", doi="10/rfwd")],
        })

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert len(updated) == 1
        assert updated[0].id == "02-backward"
        titles = {w.title for w in updated[0].works}
        assert titles == {"Ref from BWD", "Ref from FWD"}

    def it_does_not_re_snowball_already_snowballed_papers(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        repo.save_decisions("00-start", [_decision("sha1:7775895baced66ce", "r1", Verdict.ACCEPT)])
        provider = FakeProvider(refs={"sha1:7775895baced66ce": [_ref("Ref", doi="10/ref")]})

        repo.run_global_snowballing(SetKind.BACKWARD, provider)
        updated2 = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert updated2 == []

    def it_deduplicates_results_from_multiple_sources(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        repo.save_decisions("00-start", [
            _decision("sha1:7775895baced66ce", "r1", Verdict.ACCEPT),
            _decision("sha1:cdc005a8929a82bf", "r1", Verdict.ACCEPT),
        ])
        shared_ref = _ref("Shared Ref", doi="10/shared")
        provider = FakeProvider(refs={"sha1:7775895baced66ce": [shared_ref], "sha1:cdc005a8929a82bf": [shared_ref]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert len(updated) == 1
        assert len(updated[0].works) == 1
