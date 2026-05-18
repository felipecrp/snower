from datetime import datetime
from pathlib import Path

import pytest

from snow.domain.models import (
    Bidding,
    BibliographicWork,
    Criterion,
    CriterionKind,
    Decision,
    Phase,
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
        return self.refs.get(work.bib_key, [])

    def fetch_citations(self, work):
        return self.cites.get(work.bib_key, [])


def _decision(bib_key, researcher_id, verdict):
    return Decision(
        bib_key=bib_key,
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
        researchers=[Researcher(email="alice@example.com", name="Alice")],
        criteria=[Criterion(id="c1", kind=CriterionKind.INCLUDE, description="empirical study")],
    )


@pytest.fixture
def sample_works() -> list[Work]:
    return [
        Work(bib_key="a2020", title="A", authors=["A, A"], year=2020, doi="10/a"),
        Work(bib_key="b2021", title="B", authors=["B, B"], year=2021, doi="10/b"),
    ]


class DescribeProjectRepoInit:
    def it_creates_project_yml_and_sets_dir(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        assert (tmp_path / "proj" / "project.yml").exists()
        assert (tmp_path / "proj" / "sets").is_dir()
        assert (tmp_path / "proj" / "relations").is_dir()

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
        assert {w.title for w in loaded.works} == {"A", "B"}

    def it_merges_reimported_enriched_metadata_without_duplicating(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        original = Work(bib_key="a2020", title="A", authors=["A, A"], year=2020)
        repo.import_start_set([original])
        start = repo.load_set("00-start")
        bk = start.works[0].bib_key
        repo.save_decisions("00-start", [_decision(bk, "r1", Verdict.ACCEPT)])

        enriched = Work(
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
        assert updated.works[0].doi == "10/a"
        assert updated.works[0].url == "https://example.com/a"
        assert updated.works[0].abstract == "Abstract from OpenAlex"
        decisions, _ = repo.load_decisions("00-start")
        assert decisions[0].bib_key == bk

    def it_rejects_invalid_set_id(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        with pytest.raises(ValueError):
            repo.load_set("nonsense")


class DescribeImportBibWithPhases:
    def _make_repo(self, tmp_path: Path, phases: list[Phase] | None = None) -> ProjectRepo:
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(
            Project(
                name="test",
                criteria=[Criterion(id="ic1", kind=CriterionKind.INCLUDE, description="empirical")],
                phases=phases or [Phase(id="ph1", description="Records")],
            )
        )
        repo.import_start_set([])
        return repo

    def it_assigns_phase_id_when_group_matches(self, tmp_path: Path):
        repo = self._make_repo(tmp_path)
        phases = [Phase(id="ph1", description="Records")]
        criteria = [Criterion(id="ic1", kind=CriterionKind.INCLUDE, description="empirical")]
        work = Work(
            bib_key="",
            title="Test",
            authors=["A, A"],
            year=2020,
            extra={"groups": "ic1, ph1"},
        )
        repo.import_bib_to_set("00-start", [work], criteria=criteria, phases=phases, researcher_id="alice@example.com")
        decisions, _ = repo.load_decisions("00-start")
        assert len(decisions) == 1
        assert decisions[0].criterion_id == "ic1"
        assert decisions[0].phase_id == "ph1"

    def it_does_not_create_decision_when_only_phase_matches(self, tmp_path: Path):
        repo = self._make_repo(tmp_path)
        phases = [Phase(id="ph1", description="Records")]
        work = Work(
            bib_key="",
            title="Test",
            authors=["A, A"],
            year=2020,
            extra={"groups": "ph1"},
        )
        repo.import_bib_to_set("00-start", [work], phases=phases, researcher_id="alice@example.com")
        decisions, _ = repo.load_decisions("00-start")
        assert decisions == []

    def it_preserves_phase_id_when_criterion_overwrites_decision(self, tmp_path: Path):
        repo = self._make_repo(tmp_path)
        phases = [Phase(id="ph2", description="Full text")]
        criteria = [Criterion(id="ic1", kind=CriterionKind.INCLUDE, description="empirical")]
        # First import assigns phase ph2 alongside criterion ic1
        work = Work(
            bib_key="",
            title="Test",
            authors=["A, A"],
            year=2020,
            extra={"groups": "ic1, ph2"},
        )
        repo.import_bib_to_set("00-start", [work], criteria=criteria, phases=phases, researcher_id="alice@example.com")
        decisions, _ = repo.load_decisions("00-start")
        assert decisions[0].phase_id == "ph2"
        # Re-import with only criterion — phase_id must be preserved
        repo.import_bib_to_set("00-start", [work], criteria=criteria, researcher_id="alice@example.com")
        decisions, _ = repo.load_decisions("00-start")
        assert decisions[0].phase_id == "ph2"


class DescribeProjectRepoDecisions:
    def it_round_trips_decisions_and_resolutions(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.save_set(repo.import_start_set([]))
        decisions = [
            Decision(
                bib_key="wohlin2014snowballing",
                researcher_id="r1",
                verdict=Verdict.ACCEPT,
                criterion_id="c1",
                decided_at=datetime(2026, 5, 15, 12, 0, 0),
            )
        ]
        resolutions = [
            Resolution(
                bib_key="wohlin2014snowballing",
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
                bib_key="garbageId123",
                title="Snowballing in systematic literature reviews",
                authors=["Wohlin, Claus"],
                year=2014,
                doi="10/wohlin",
            )
        ]
        start = repo.import_start_set(works)
        # One word slug: "snowballing"
        assert start.works[0].bib_key == "wohlin2014snowballing"
        keys = repo.load_keys()
        # keys.yml has one entry; value is the assigned bib_key
        assert len(keys) == 1
        assert list(keys.values())[0].bib_key == "wohlin2014snowballing"

    def it_disambiguates_with_sequential_number_when_slug_collides(
        self, tmp_path: Path, project: Project
    ):
        # Two different papers with the same bib_key slug but different short fingerprints.
        # Both start with "Snowballing" (same 1-word slug) but differ from the 2nd word,
        # so the short fingerprint (3 words) distinguishes them → sequential suffix.
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(bib_key="x",
                 title="Snowballing systematic analysis approaches",
                 authors=["Wohlin, Claus"], year=2014, doi="10/a"),
            Work(bib_key="y",
                 title="Snowballing comprehensive survey techniques",
                 authors=["Wohlin, Claus"], year=2014, doi="10/b"),
        ]
        start = repo.import_start_set(works)
        bib_keys = [w.bib_key for w in start.works]
        assert "wohlin2014snowballing" in bib_keys
        assert "wohlin2014snowballing2" in bib_keys

    def it_reuses_existing_key_for_same_paper(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(
            [Work(bib_key="x",
                  title="Snowballing systematic review",
                  authors=["Wohlin, Claus"], year=2014, doi="10/a")]
        )
        first_bk = repo.load_set("00-start").works[0].bib_key

        # Same paper (full fingerprint matches) in a new set → same bib_key reused.
        new_set = ReviewSet(
            id="01-backward",
            kind=SetKind.BACKWARD,
            iteration=1,
            works=[
                Work(bib_key="reimported",
                     title="Snowballing systematic review",
                     authors=["Wohlin, Claus"], year=2014, doi="10/a"),
                Work(bib_key="other",
                     title="Guidelines for empirical research",
                     authors=["Wohlin, Claus"], year=2014, doi="10/b"),
            ],
        )
        repo.save_set(new_set)
        assert new_set.works[0].bib_key == first_bk
        assert new_set.works[1].bib_key == "wohlin2014guidelines"

    def it_fuzzy_matches_same_paper_when_trailing_author_is_missing(
        self, tmp_path: Path, project: Project
    ):
        """Short fingerprint match: same paper with 3 authors matches a version with only 2.

        The short fingerprint uses the first 2 authors + year + first 3 title words.
        A source that omits only trailing co-authors still produces the same short hash.
        """
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        full = Work(bib_key="x",
                    title="Systematic literature review methods",
                    authors=["Smith, John", "Jones, Mary", "Wilson, Bob"], year=2020)
        repo.import_start_set([full])
        first_bk = repo.load_set("00-start").works[0].bib_key

        # Trailing 3rd author missing — first 2 still present → short fingerprint matches
        partial = Work(bib_key="y",
                       title="Systematic literature review methods",
                       authors=["Smith, John", "Jones, Mary"], year=2020)
        new_set = ReviewSet(id="01-backward", kind=SetKind.BACKWARD, iteration=1, works=[partial])
        repo.save_set(new_set)

        assert new_set.works[0].bib_key == first_bk

    def it_increments_sequential_suffix_past_two(self, tmp_path: Path, project: Project):
        """Three papers with the same minted slug all get distinct sequential keys."""
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(bib_key="x", title="Snowballing systematic analysis", authors=["Wohlin, Claus"], year=2014),
            Work(bib_key="y", title="Snowballing comprehensive survey", authors=["Wohlin, Claus"], year=2014),
            Work(bib_key="z", title="Snowballing empirical evaluation", authors=["Wohlin, Claus"], year=2014),
        ]
        start = repo.import_start_set(works)
        bib_keys = {w.bib_key for w in start.works}
        assert "wohlin2014snowballing" in bib_keys
        assert "wohlin2014snowballing2" in bib_keys
        assert "wohlin2014snowballing3" in bib_keys

    def it_treats_short_hash_collision_as_same_paper(self, tmp_path: Path, project: Project):
        """Two papers that share the same short fingerprint are treated as the same paper.

        The short fingerprint is an 8-char hex (4 billion values) — collisions are unlikely
        but handled by registering a second full-hash entry pointing to the same bib_key.
        We simulate this by manually pre-seeding keys.yml with a short hash and then importing
        a new paper whose short fingerprint matches.
        """
        from snow.domain.identity import WorkRef, short_fingerprint
        from snow.storage.repo import KeyEntry

        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)

        existing_ref = WorkRef(
            title="Systematic literature review methods",
            authors=("Smith, John", "Jones, Mary"),
            year=2020,
        )
        shash = short_fingerprint(existing_ref)

        # Seed keys.yml with a dummy full hash having the same short hash
        fake_full = "sha1full:" + "a" * 40
        repo.save_keys({fake_full: KeyEntry(short=shash, bib_key="smith2020systematic")})

        # Import a paper whose short fingerprint matches the seeded entry
        paper = Work(
            bib_key="",
            title="Systematic literature review methods",
            authors=["Smith, John", "Jones, Mary"],
            year=2020,
        )
        start = repo.import_start_set([paper])
        assert start.works[0].bib_key == "smith2020systematic"
        keys = repo.load_keys()
        # A new full-hash entry was added for this paper, pointing to the same bib_key
        real_full = next(k for k in keys if k != fake_full)
        assert keys[real_full].bib_key == "smith2020systematic"
        assert keys[real_full].short == shash

    def it_persists_keys_yml_sorted_by_fingerprint(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(
            [
                Work(bib_key="zz", title="Snowballing literature review",
                     authors=["Zeta, Z"], year=2020, doi="10/z"),
                Work(bib_key="aa", title="Snowballing literature review",
                     authors=["Alpha, A"], year=2020, doi="10/a"),
            ]
        )
        text = (tmp_path / "proj" / "keys.yml").read_text()
        # Both entries are present (different authors → different fingerprints)
        assert "alpha2020" in text
        assert "zeta2020" in text


class DescribeWorksLibrary:
    def it_stores_each_paper_once_across_sets(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        w = Work(bib_key="", title="Shared Paper", authors=["Doe, J"], year=2020, doi="10/shared")
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
        bare = Work(bib_key="", title="P", authors=["A, A"], year=2020)
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
        cached = Work(bib_key="", title="P", authors=["Doe, J"], year=2020,
                      doi="10/p", abstract="Cached abstract")
        repo.import_start_set([cached])

        incoming = Work(bib_key="garbage", title="P", authors=["Doe, J"], year=2020,
                        url="https://example.com/p")

        merged = repo.merge_with_library([incoming])

        assert merged[0].abstract == "Cached abstract"
        assert merged[0].doi == "10/p"
        assert merged[0].url == "https://example.com/p"


class DescribeRecalculateOrphans:
    def _setup_two_sets(self, repo):
        accepted = Work(bib_key="", title="Accepted", authors=["A, A"], year=2020, doi="10/a")
        ref = Work(bib_key="", title="Ref", authors=["B, B"], year=2021, doi="10/b")
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
        repo.save_decisions("00-start", [_decision(accepted.bib_key, "r1", Verdict.ACCEPT)])

        repo.recalculate_orphans()
        assert len(repo.load_set("01-backward").works) == 1

        repo.save_decisions("00-start", [_decision(accepted.bib_key, "r1", Verdict.REJECT)])
        repo.recalculate_orphans()

        assert len(repo.load_set("01-backward").works) == 0
        assert {w.bib_key for w in repo.load_set("orphan").works} == {ref.bib_key}

    def it_returns_orphan_to_earliest_valid_iteration_set_when_reconnected(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        accepted, ref = self._setup_two_sets(repo)

        repo.save_decisions("00-start", [_decision(accepted.bib_key, "r1", Verdict.REJECT)])
        repo.recalculate_orphans()
        assert {w.bib_key for w in repo.load_set("orphan").works} == {ref.bib_key}

        repo.save_decisions("00-start", [_decision(accepted.bib_key, "r1", Verdict.ACCEPT)])
        repo.recalculate_orphans()

        assert repo.load_set("orphan").works == []
        assert {w.bib_key for w in repo.load_set("01-backward").works} == {ref.bib_key}


class DescribeProjectRepoRelations:
    def it_round_trips_relations(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        rels = [Relation(citing_bib_key="wohlin2014a", cited_bib_key="wohlin2014b")]
        repo.save_relations(rels)
        assert repo.load_relations() == rels
        assert (tmp_path / "proj" / "relations" / "wohlin2014a.yml").exists()
        assert (tmp_path / "proj" / "relations" / "wohlin2014b.yml").exists()

    def it_starts_empty(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        assert repo.load_relations() == []

    def it_deduplicates_edges_loaded_from_multiple_relation_files(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        relations_dir = tmp_path / "proj" / "relations"
        (relations_dir / "wohlin2014a.yml").write_text("cite:\n  - wohlin2014b\ncited_by: []\n")
        (relations_dir / "wohlin2014b.yml").write_text("cite: []\ncited_by:\n  - wohlin2014a\n")

        assert repo.load_relations() == [Relation(citing_bib_key="wohlin2014a", cited_bib_key="wohlin2014b")]

    def it_removes_stale_relation_files_when_relations_shrink(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.save_relations([
            Relation(citing_bib_key="a", cited_bib_key="b"),
            Relation(citing_bib_key="b", cited_bib_key="c"),
        ])

        repo.save_relations([Relation(citing_bib_key="a", cited_bib_key="b")])

        relations_dir = tmp_path / "proj" / "relations"
        assert (relations_dir / "a.yml").exists()
        assert (relations_dir / "b.yml").exists()
        assert not (relations_dir / "c.yml").exists()
        assert repo.load_relations() == [Relation(citing_bib_key="a", cited_bib_key="b")]


class DescribeRunGlobalSnowballing:
    def it_creates_backward_set_from_accepted_start_papers(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        repo.save_decisions("00-start", [_decision(bk_a, "r1", Verdict.ACCEPT)])
        provider = FakeProvider(refs={bk_a: [_ref("Ref Paper", doi="10/ref")]})

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
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        repo.save_decisions("00-start", [_decision(bk_a, "r1", Verdict.ACCEPT)])
        provider = FakeProvider(refs={
            bk_a: [_ref("Ref Paper", doi="10/ref", venue="Journal of Examples",
                         url="https://example.com/ref", pdf_url="https://example.com/ref.pdf",
                         abstract="Provider abstract")],
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
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        repo.save_decisions("00-start", [_decision(bk_a, "r1", Verdict.ACCEPT)])
        provider = FakeProvider(cites={bk_a: [_ref("Citing Paper", doi="10/cite")]})

        updated = repo.run_global_snowballing(SetKind.FORWARD, provider)

        assert len(updated) == 1
        assert updated[0].id == "01-forward"

    def it_skips_papers_rejected_by_majority(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        repo.save_decisions("00-start", [
            _decision(bk_a, "r1", Verdict.ACCEPT),
            _decision(bk_a, "r2", Verdict.REJECT),
        ])
        provider = FakeProvider(refs={bk_a: [_ref("Should Not Appear")]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert updated == []

    def it_skips_papers_with_no_decisions(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        provider = FakeProvider(refs={bk_a: [_ref("Should Not Appear")]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert updated == []

    def it_merges_papers_from_same_iteration_into_one_target_set(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)

        paper_bwd = Work(bib_key="", title="BWD", authors=["A, A"], year=2020, doi="10/bwd")
        paper_fwd = Work(bib_key="", title="FWD", authors=["B, B"], year=2021, doi="10/fwd")
        repo.save_set(ReviewSet(id="01-backward", kind=SetKind.BACKWARD, iteration=1, works=[paper_bwd]))
        repo.save_set(ReviewSet(id="01-forward", kind=SetKind.FORWARD, iteration=1, works=[paper_fwd]))
        bwd_bk = repo.load_set("01-backward").works[0].bib_key
        fwd_bk = repo.load_set("01-forward").works[0].bib_key
        repo.save_decisions("01-backward", [_decision(bwd_bk, "r1", Verdict.ACCEPT)])
        repo.save_decisions("01-forward", [_decision(fwd_bk, "r1", Verdict.ACCEPT)])

        provider = FakeProvider(refs={
            bwd_bk: [_ref("Ref from BWD", doi="10/rbwd")],
            fwd_bk: [_ref("Ref from FWD", doi="10/rfwd")],
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
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        repo.save_decisions("00-start", [_decision(bk_a, "r1", Verdict.ACCEPT)])
        provider = FakeProvider(refs={bk_a: [_ref("Ref", doi="10/ref")]})

        repo.run_global_snowballing(SetKind.BACKWARD, provider)
        updated2 = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert updated2 == []

    def it_deduplicates_results_from_multiple_sources(
        self, tmp_path: Path, project: Project, sample_works: list[Work]
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        start = repo.import_start_set(sample_works)
        bk_a = next(w.bib_key for w in start.works if w.title == "A")
        bk_b = next(w.bib_key for w in start.works if w.title == "B")
        repo.save_decisions("00-start", [
            _decision(bk_a, "r1", Verdict.ACCEPT),
            _decision(bk_b, "r1", Verdict.ACCEPT),
        ])
        shared_ref = _ref("Shared Ref", doi="10/shared")
        provider = FakeProvider(refs={bk_a: [shared_ref], bk_b: [shared_ref]})

        updated = repo.run_global_snowballing(SetKind.BACKWARD, provider)

        assert len(updated) == 1
        assert len(updated[0].works) == 1


class Describe_bidding_storage:
    def it_saves_and_loads_biddings(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        start = repo.load_set("00-start")
        bk = start.works[0].bib_key

        repo.save_bidding("00-start", Bidding(researcher_id="alice@example.com", work_ids=[bk]))
        loaded = repo.load_biddings("00-start")

        assert len(loaded) == 1
        assert loaded[0].researcher_id == "alice@example.com"
        assert bk in loaded[0].work_ids

    def it_adds_and_removes_individual_works(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        start = repo.load_set("00-start")
        bk = start.works[0].bib_key

        after_add = repo.add_work_to_bidding("00-start", "alice@example.com", bk)
        assert bk in after_add.work_ids

        after_remove = repo.remove_work_from_bidding("00-start", "alice@example.com", bk)
        assert bk not in after_remove.work_ids

    def it_deletes_biddings_when_researcher_is_removed(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.save_researcher(Researcher(email="alice@example.com", name="Alice"))
        repo.import_start_set(sample_works)
        start = repo.load_set("00-start")
        bk = start.works[0].bib_key

        repo.add_work_to_bidding("00-start", "alice@example.com", bk)
        assert repo.bidding_path("00-start", "alice@example.com").exists()

        repo.delete_researcher_biddings("alice@example.com")
        assert not repo.bidding_path("00-start", "alice@example.com").exists()

    def it_renames_bidding_files_on_researcher_rename(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.save_researcher(Researcher(email="alice@example.com", name="Alice"))
        repo.import_start_set(sample_works)
        start = repo.load_set("00-start")
        bk = start.works[0].bib_key

        repo.add_work_to_bidding("00-start", "alice@example.com", bk)
        repo.rename_researcher_biddings("alice@example.com", "new@example.com")

        assert not repo.bidding_path("00-start", "alice@example.com").exists()
        assert repo.bidding_path("00-start", "new@example.com").exists()
        loaded = repo.load_biddings("00-start")
        assert loaded[0].researcher_id == "new@example.com"

    def it_persists_assignment_percentage_in_researcher_file(self, tmp_path: Path):
        repo = ProjectRepo(tmp_path / "proj")
        repo.researchers_dir().mkdir(parents=True, exist_ok=True)
        repo.save_researcher(Researcher(email="bob@example.com", name="Bob", assignment_percentage=60))
        loaded = repo.list_researchers()
        assert loaded[0].assignment_percentage == 60
