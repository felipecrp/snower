import pytest
import yaml

from snower import PaperSet, Project, parse_bibtex

_BIB = """\
@article{kitchenham2009,
  author = {Kitchenham, Barbara},
  title = {Systematic Literature Reviews in Software Engineering},
  year = {2009},
  doi = {10.1234/example},
}

@article{beethoven1827,
  author = {Ludwig van Beethoven and Wolfgang Amadeus Mozart},
  title = {Classical Music Theory},
  year = {1827},
}
"""

_BIB_NO_BIB_ID = """\
@article{noauthor2024,
  title = {A Title Without Author},
  year = {2024},
}
"""


class DescribePaperSet:
    def it_has_a_name_and_round(self):
        ps = PaperSet(name="seed", round=0)
        assert ps.name == "seed"
        assert ps.round == 0
        assert ps.paper_ids == set()

    def it_adds_a_paper_id(self):
        ps = PaperSet(name="seed", round=0)
        ps.add("kitchenham2009systematic")
        assert "kitchenham2009systematic" in ps.paper_ids

    def it_ignores_duplicate_paper_ids(self):
        ps = PaperSet(name="seed", round=0)
        ps.add("kitchenham2009systematic")
        ps.add("kitchenham2009systematic")
        assert len(ps.paper_ids) == 1


class DescribeProject:
    def it_has_a_name_path_papers_and_sets(self, tmp_path):
        project = Project(name="my-project", path=tmp_path)
        assert project.name == "my-project"
        assert project.path == tmp_path
        assert project.papers == {}
        assert project.paper_sets == {}

    def it_adds_a_paper_keyed_by_bib_id(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_paper(paper)
        assert paper.bib_id in project.papers
        assert project.papers[paper.bib_id] == paper

    def it_raises_when_bib_id_missing(self, tmp_path):
        paper = parse_bibtex(_BIB_NO_BIB_ID)[0]
        project = Project(name="p", path=tmp_path)
        with pytest.raises(ValueError, match="bib_id"):
            project.add_paper(paper)

    def it_adds_a_paper_to_a_set_and_resolves_it(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_to_set("seed", paper)
        assert project.papers_in("seed") == [paper]

    def it_raises_when_set_missing_on_add_to_set(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.add_to_set("nonexistent", paper)

    def it_writes_project_yml_and_papers_dir(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_to_set("seed", paper)
        project.save()
        assert (tmp_path / "project.yml").exists()
        assert (tmp_path / "papers" / f"{paper.bib_id}.yml").exists()

    def it_round_trips_a_project(self, tmp_path):
        papers = parse_bibtex(_BIB)
        project = Project(name="slr", path=tmp_path)
        project.add_set("seed", 0)
        for p in papers:
            project.add_to_set("seed", p)
        project.save()

        loaded = Project.load(tmp_path)
        assert loaded.name == project.name
        assert loaded.path == project.path
        assert set(loaded.papers.keys()) == set(project.papers.keys())
        assert loaded.paper_sets["seed"].round == 0
        assert loaded.paper_sets["seed"].paper_ids == project.paper_sets["seed"].paper_ids

    def it_raises_when_adding_paper_already_in_another_set(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_set("round1", 1)
        project.add_to_set("seed", paper)
        with pytest.raises(ValueError, match="already belongs to set"):
            project.add_to_set("round1", paper)

    def it_allows_readding_paper_to_same_set(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_to_set("seed", paper)
        project.add_to_set("seed", paper)
        assert len(project.paper_sets["seed"].paper_ids) == 1

    def it_returns_the_set_a_paper_belongs_to(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_to_set("seed", paper)
        assert project.set_of(paper.bib_id) == "seed"

    def it_returns_none_when_paper_belongs_to_no_set(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_paper(paper)
        assert project.set_of(paper.bib_id) is None

    def it_moves_paper_from_one_set_to_another(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_set("round1", 1)
        project.add_to_set("seed", paper)
        project.move_to_set("round1", paper)
        assert project.set_of(paper.bib_id) == "round1"
        assert paper.bib_id not in project.paper_sets["seed"].paper_ids

    def it_move_to_same_set_is_noop(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_to_set("seed", paper)
        project.move_to_set("seed", paper)
        assert project.set_of(paper.bib_id) == "seed"
        assert len(project.paper_sets["seed"].paper_ids) == 1

    def it_raises_on_move_to_nonexistent_set(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.move_to_set("nonexistent", paper)

    def it_omits_path_and_paper_contents_from_project_yml(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        project = Project(name="p", path=tmp_path)
        project.add_set("seed", 0)
        project.add_to_set("seed", paper)
        project.save()

        data = yaml.safe_load((tmp_path / "project.yml").read_text(encoding="utf-8"))
        assert "name" in data
        assert "paper_sets" in data
        assert "path" not in data
        assert "papers" not in data
