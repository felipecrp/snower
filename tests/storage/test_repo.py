from datetime import datetime
from pathlib import Path

import pytest

from snow.domain.models import (
    Criterion,
    CriterionKind,
    Decision,
    Project,
    Relation,
    Researcher,
    Resolution,
    SetKind,
    Verdict,
    Work,
)
from snow.storage.repo import ProjectRepo


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
        Work(id="doi:10/a", bib_key="a2020", title="A", authors=["A, A"], year=2020, doi="10/a"),
        Work(id="doi:10/b", bib_key="b2021", title="B", authors=["B, B"], year=2021, doi="10/b"),
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
        assert {w.id for w in loaded.works} == {"doi:10/a", "doi:10/b"}

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
                work_id="doi:10/a",
                researcher_id="r1",
                verdict=Verdict.ACCEPT,
                criterion_id="c1",
                decided_at=datetime(2026, 5, 15, 12, 0, 0),
            )
        ]
        resolutions = [
            Resolution(
                work_id="doi:10/a",
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
                id="doi:10/wohlin",
                bib_key="garbageId123",
                title="Snowballing",
                authors=["Wohlin, Claus"],
                year=2014,
                doi="10/wohlin",
            )
        ]
        start = repo.import_start_set(works)
        assert start.works[0].bib_key == "wohlin2014a"
        assert repo.load_keys() == {"wohlin2014a": "doi:10/wohlin"}

    def it_disambiguates_with_letters_for_same_author_year(
        self, tmp_path: Path, project: Project
    ):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        works = [
            Work(id="doi:10/a", bib_key="x", title="T1", authors=["Wohlin, Claus"], year=2014, doi="10/a"),
            Work(id="doi:10/b", bib_key="y", title="T2", authors=["Wohlin, Claus"], year=2014, doi="10/b"),
            Work(id="doi:10/c", bib_key="z", title="T3", authors=["Wohlin, Claus"], year=2014, doi="10/c"),
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
            [Work(id="doi:10/a", bib_key="x", title="T", authors=["Wohlin, Claus"], year=2014, doi="10/a")]
        )
        new_set = ReviewSet(
            id="01-backward",
            kind=Kind.BACKWARD,
            iteration=1,
            works=[
                Work(id="doi:10/a", bib_key="reimported", title="T", authors=["Wohlin"], year=2014, doi="10/a"),
                Work(id="doi:10/b", bib_key="other", title="U", authors=["Wohlin, Claus"], year=2014, doi="10/b"),
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
                Work(id="doi:10/z", bib_key="zz", title="Z", authors=["Zeta, Z"], year=2020, doi="10/z"),
                Work(id="doi:10/a", bib_key="aa", title="A", authors=["Alpha, A"], year=2020, doi="10/a"),
            ]
        )
        text = (tmp_path / "proj" / "keys.yml").read_text()
        assert text.index("alpha2020a") < text.index("zeta2020a")


class DescribeProjectRepoRelations:
    def it_round_trips_relations(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        rels = [Relation(citing_work_id="doi:10/a", cited_work_id="doi:10/b")]
        repo.save_relations(rels)
        assert repo.load_relations() == rels

    def it_starts_empty(self, tmp_path: Path, project: Project):
        repo = ProjectRepo(tmp_path / "proj")
        repo.init(project)
        assert repo.load_relations() == []
