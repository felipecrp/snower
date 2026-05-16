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
        assert (tmp_path / "proj" / "sets" / "00-start" / "articles.bib").exists()

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

    def it_starts_snowballing_set(self, tmp_path: Path, project: Project, sample_works: list[Work]):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(sample_works)
        backward = repo.start_snowballing("00-start", SetKind.BACKWARD)
        assert backward.id == "01-backward"
        assert backward.kind == SetKind.BACKWARD
        assert backward.iteration == 1
        assert backward.parent_set_id == "00-start"
        assert backward.works == []
        assert repo.load_set("01-backward").parent_set_id == "00-start"

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
    def it_renames_imported_keys_to_surname_year_letter(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(
                id="sha1:7a611379c566500f",
                bib_key="garbageId123",
                title="Snowballing",
                authors=["Wohlin, Claus"],
                year=2014,
                doi="10/wohlin",
            )
        ]
        start = repo.import_start_set(works)
        assert start.works[0].bib_key == "wohlin2014a"
        assert repo.load_keys() == {"wohlin2014a": "sha1:7a611379c566500f"}

    def it_disambiguates_with_letters_for_same_author_year(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(id="sha1:23440077d4c90157", bib_key="x", title="T1", authors=["Wohlin, Claus"], year=2014, doi="10/a"),
            Work(id="sha1:a30b2382d7a2ea0f", bib_key="y", title="T2", authors=["Wohlin, Claus"], year=2014, doi="10/b"),
            Work(id="sha1:65b4f475f6256261", bib_key="z", title="T3", authors=["Wohlin, Claus"], year=2014, doi="10/c"),
        ]
        start = repo.import_start_set(works)
        assert [w.bib_key for w in start.works] == ["wohlin2014a", "wohlin2014b", "wohlin2014c"]

    def it_reuses_existing_key_when_work_id_already_known(
        self, tmp_path: Path, project: Project
    ):
        from snow.domain.models import Set as ReviewSet
        from snow.domain.models import SetKind as Kind

        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(
            [Work(id="sha1:1b7d6438c9db5159", bib_key="x", title="T", authors=["Wohlin, Claus"], year=2014, doi="10/a")]
        )
        new_set = ReviewSet(
            id="01-backward",
            kind=Kind.BACKWARD,
            iteration=1,
            works=[
                Work(id="sha1:1b7d6438c9db5159", bib_key="reimported", title="T", authors=["Wohlin"], year=2014, doi="10/a"),
                Work(id="sha1:fbb4c753aeb8d236", bib_key="other", title="U", authors=["Wohlin, Claus"], year=2014, doi="10/b"),
            ],
        )
        repo.save_set(new_set)
        assert new_set.works[0].bib_key == "wohlin2014a"
        assert new_set.works[1].bib_key == "wohlin2014b"

    def it_persists_keys_yml_sorted(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        repo.import_start_set(
            [
                Work(id="sha1:1f3edef7e27228c2", bib_key="zz", title="Z", authors=["Zeta, Z"], year=2020, doi="10/z"),
                Work(id="sha1:7775895baced66ce", bib_key="aa", title="A", authors=["Alpha, A"], year=2020, doi="10/a"),
            ]
        )
        text = (tmp_path / "proj" / "keys.yml").read_text()
        assert text.index("alpha2020a") < text.index("zeta2020a")


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
