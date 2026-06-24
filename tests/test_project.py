import pytest
import yaml

from snower import Author, Paper, PaperSet, Project


def _paper(bib_id: str) -> Paper:
    """A minimal in-memory paper with a usable bib_id."""
    return Paper(bib_id=bib_id, title=f"Title {bib_id}")


def _full_paper(bib_id: str) -> Paper:
    """A persistable paper (all repository-required fields present)."""
    return Paper(bib_id=bib_id, title=f"Title {bib_id}", year=2020, authors=[Author(family=bib_id)])


def _project_with(tmp_path, *bib_ids: str, seed: str) -> Project:
    """A project whose `seed` is a seed and the rest plain papers."""
    project = Project(name="p", path=tmp_path)
    project.add_seed(_paper(seed))
    for bib_id in bib_ids:
        if bib_id != seed:
            project.add_paper(_paper(bib_id))
    return project


class DescribePaperSet:
    def it_has_a_name_and_round(self):
        ps = PaperSet(name="backward", round=1)
        assert ps.name == "backward"
        assert ps.round == 1
        assert ps.paper_ids == set()

    def it_adds_a_paper_id(self):
        ps = PaperSet(name="start", round=0)
        ps.add("kitchenham2009systematic")
        assert "kitchenham2009systematic" in ps.paper_ids

    def it_ignores_duplicate_paper_ids(self):
        ps = PaperSet(name="start", round=0)
        ps.add("kitchenham2009systematic")
        ps.add("kitchenham2009systematic")
        assert len(ps.paper_ids) == 1


class DescribeProject:
    def it_has_a_name_path_papers_and_seeds(self, tmp_path):
        project = Project(name="my-project", path=tmp_path)
        assert project.name == "my-project"
        assert project.path == tmp_path
        assert project.papers == {}
        assert project.seeds == set()

    def it_adds_a_paper_keyed_by_bib_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_paper(_paper("kitchenham2009"))
        assert "kitchenham2009" in project.papers

    def it_raises_when_bib_id_missing(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(ValueError, match="bib_id"):
            project.add_paper(Paper(title="No bib id"))

    def it_registers_a_seed(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_seed(_paper("seed"))
        assert "seed" in project.seeds
        assert "seed" in project.papers


class DescribeSnowball:
    def it_places_a_seed_at_start_0(self, tmp_path):
        project = _project_with(tmp_path, seed="seed")
        assert project.set_of("seed") == "start-0"

    def it_places_a_seeds_reference_at_backward_1(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        project.add_reference("seed", "a")
        assert project.set_of("a") == "backward-1"

    def it_places_a_seeds_citation_at_forward_1(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        project.add_citation("seed", "a")
        assert project.set_of("a") == "forward-1"

    def it_increments_round_along_a_chain(self, tmp_path):
        project = _project_with(tmp_path, "a", "x", seed="seed")
        project.add_reference("seed", "a")
        project.add_reference("a", "x")
        assert project.set_of("a") == "backward-1"
        assert project.set_of("x") == "backward-2"

    def it_takes_the_minimum_round_across_parents(self, tmp_path):
        # a@1 cites x; b@4 references x -> x is backward-2 (min over parents).
        project = _project_with(tmp_path, "a", "x", "c1", "c2", "c3", "b", seed="seed")
        project.add_reference("seed", "a")
        project.add_reference("a", "x")
        for parent, child in [("seed", "c1"), ("c1", "c2"), ("c2", "c3"), ("c3", "b")]:
            project.add_reference(parent, child)
        project.add_reference("b", "x")
        # x keeps its minimum round via a, regardless of the longer b path.
        assert project.set_of("x") == "backward-2"

    def it_moves_a_subtree_down_when_a_shorter_edge_is_added(self, tmp_path):
        project = _project_with(tmp_path, "a", "b", "x", seed="seed")
        project.add_reference("seed", "a")
        project.add_reference("a", "b")
        project.add_reference("b", "x")
        assert project.set_of("x") == "backward-3"
        # A shorter edge from the seed reroutes x's whole subtree down a round.
        project.add_reference("seed", "b")
        assert project.set_of("b") == "backward-1"
        assert project.set_of("x") == "backward-2"

    def it_prefers_backward_on_a_same_round_tie(self, tmp_path):
        project = _project_with(tmp_path, "p1", "q", "x", seed="seed")
        project.add_reference("seed", "p1")
        project.add_reference("p1", "x")  # x: backward-2
        project.add_citation("seed", "q")  # q cites seed -> q: forward-1
        project.add_reference("x", "q")  # x cites q -> candidate forward-2
        assert project.set_of("x") == "backward-2"

    def it_keeps_placement_when_an_equal_length_path_survives(self, tmp_path):
        project = _project_with(tmp_path, "p1", "p2", "x", seed="seed")
        project.add_reference("seed", "p1")
        project.add_reference("seed", "p2")
        project.add_reference("p1", "x")
        project.add_reference("p2", "x")
        assert project.set_of("x") == "backward-2"
        project.exclude("p1")
        assert project.set_of("x") == "backward-2"  # still reached via p2

    def it_excludes_and_redrives_then_reincludes(self, tmp_path):
        project = _project_with(tmp_path, "a", "x", "c1", "c2", "c3", "b", seed="seed")
        project.add_reference("seed", "a")
        project.add_reference("a", "x")
        for parent, child in [("seed", "c1"), ("c1", "c2"), ("c2", "c3"), ("c3", "b")]:
            project.add_reference(parent, child)
        project.add_reference("b", "x")
        assert project.set_of("x") == "backward-2"

        project.exclude("a")
        assert project.set_of("x") == "backward-5"  # re-derived via b@4
        project.exclude("b")
        assert project.set_of("x") == "orphan--1"  # no included path
        project.include("a")
        assert project.set_of("x") == "backward-2"  # back through a

    def it_keeps_an_excluded_papers_own_set(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        project.add_reference("seed", "a")
        project.exclude("a")
        assert project.set_of("a") == "backward-1"

    def it_orphans_papers_with_no_path_to_a_seed(self, tmp_path):
        project = _project_with(tmp_path, "lonely", seed="seed")
        assert project.set_of("lonely") == "orphan--1"

    def it_raises_when_an_edge_endpoint_is_missing(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        with pytest.raises(KeyError):
            project.add_reference("seed", "ghost")

    def it_raises_on_self_citation(self, tmp_path):
        project = _project_with(tmp_path, seed="seed")
        with pytest.raises(ValueError, match="cannot cite itself"):
            project.add_reference("seed", "seed")

    def it_records_the_same_edge_via_add_citation(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        project.add_citation("a", "seed")  # seed cites a, stored on a.citations
        assert project.set_of("a") == "backward-1"

    def it_resolves_references_of_from_both_stored_sides(self, tmp_path):
        project = _project_with(tmp_path, "a", "b", seed="seed")
        project.add_reference("seed", "a")  # stored on seed.references
        project.add_citation("b", "seed")  # seed cites b, stored on b.citations
        refs = {p.bib_id for p in project.references_of("seed")}
        assert refs == {"a", "b"}

    def it_resolves_citations_of_from_both_stored_sides(self, tmp_path):
        project = _project_with(tmp_path, "a", "b", seed="seed")
        project.add_citation("seed", "a")  # a cites seed, stored on seed.citations
        project.add_reference("b", "seed")  # b cites seed, stored on b.references
        cites = {p.bib_id for p in project.citations_of("seed")}
        assert cites == {"a", "b"}


class DescribeProjectPersistence:
    def _saved_project(self, tmp_path) -> Project:
        project = Project(name="slr", path=tmp_path)
        project.add_seed(_full_paper("seed"))
        project.add_paper(_full_paper("a"))
        project.add_reference("seed", "a")
        project.save()
        return project

    def it_writes_project_yml_papers_and_sets(self, tmp_path):
        self._saved_project(tmp_path)
        assert (tmp_path / "project.yml").exists()
        assert (tmp_path / "papers" / "seed.yml").exists()
        assert (tmp_path / "sets" / "start-0.yml").exists()
        assert (tmp_path / "sets" / "backward-1.yml").exists()

    def it_writes_seeds_but_no_paper_sets_in_project_yml(self, tmp_path):
        self._saved_project(tmp_path)
        data = yaml.safe_load((tmp_path / "project.yml").read_text(encoding="utf-8"))
        assert data["name"] == "slr"
        assert data["seeds"] == ["seed"]
        assert "paper_sets" not in data
        assert "path" not in data
        assert "papers" not in data

    def it_removes_a_set_file_when_it_empties(self, tmp_path):
        project = self._saved_project(tmp_path)
        assert (tmp_path / "sets" / "backward-1.yml").exists()
        # Excluding does not empty a set, but adding a shorter path that moves the
        # only member out of backward-1 should remove the stale file on re-save.
        project.add_citation("seed", "a")  # now a also forward-1; still placed backward-1
        # Re-route: make a a seed's citation only by removing the reference path.
        project.papers["seed"].references.discard("a")
        project._rederive()
        project.save()
        assert not (tmp_path / "sets" / "backward-1.yml").exists()
        assert (tmp_path / "sets" / "forward-1.yml").exists()

    def it_round_trips_seeds_edges_inclusion_and_placement(self, tmp_path):
        project = Project(name="slr", path=tmp_path)
        project.add_seed(_full_paper("seed"))
        for bib_id in ("a", "b", "x"):
            project.add_paper(_full_paper(bib_id))
        project.add_reference("seed", "a")
        project.add_reference("a", "x")
        project.add_reference("seed", "b")
        project.exclude("b")
        project.save()

        loaded = Project.load(tmp_path)
        assert loaded.name == project.name
        assert loaded.seeds == project.seeds
        assert loaded.papers["seed"].references == {"a", "b"}
        assert loaded.papers["b"].included is False
        assert loaded.set_of("seed") == "start-0"
        assert loaded.set_of("a") == "backward-1"
        assert loaded.set_of("x") == "backward-2"
        assert loaded.set_of("b") == "backward-1"
