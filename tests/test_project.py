import pytest
import yaml

from snower import Assessment, Author, Criterion, CriterionType, Decision, DecisionStrategyType, Paper, PaperSet, Phase, Project, Researcher


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
        assert project.set_of("seed") == "start_set"

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
        project = _project_with(tmp_path, "a", "b", "x", seed="seed")
        project.add_reference("seed", "a")   # a: backward-1
        project.add_citation("seed", "b")    # b cites seed -> b: forward-1
        project.add_reference("a", "x")      # x: backward-2
        project.add_citation("b", "x")       # x cites b -> forward-2 candidate
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
        assert project.set_of("x") == "orphans"  # no included path
        project.include("a")
        assert project.set_of("x") == "backward-2"  # back through a

    def it_keeps_an_excluded_papers_own_set(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        project.add_reference("seed", "a")
        project.exclude("a")
        assert project.set_of("a") == "backward-1"

    def it_orphans_papers_with_no_path_to_a_seed(self, tmp_path):
        project = _project_with(tmp_path, "lonely", seed="seed")
        assert project.set_of("lonely") == "orphans"

    def it_raises_when_an_edge_endpoint_is_missing(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        with pytest.raises(KeyError):
            project.add_reference("seed", "ghost")

    def it_raises_on_self_citation(self, tmp_path):
        project = _project_with(tmp_path, seed="seed")
        with pytest.raises(ValueError, match="cannot cite itself"):
            project.add_reference("seed", "seed")

    def it_records_the_forward_edge_via_add_citation(self, tmp_path):
        project = _project_with(tmp_path, "a", seed="seed")
        project.add_citation("seed", "a")  # a cites seed, stored on seed.citations -> a: forward-1
        assert project.set_of("a") == "forward-1"

    def it_resolves_references_of_from_the_references_side_only(self, tmp_path):
        project = _project_with(tmp_path, "a", "b", seed="seed")
        project.add_reference("seed", "a")  # stored on seed.references
        project.add_citation("b", "seed")   # stored on b.citations, NOT on seed.references
        refs = {p.bib_id for p in project.references_of("seed")}
        assert refs == {"a"}  # b is not a backward neighbour of seed

    def it_resolves_citations_of_from_the_citations_side_only(self, tmp_path):
        project = _project_with(tmp_path, "a", "b", seed="seed")
        project.add_citation("seed", "a")  # a cites seed, stored on seed.citations
        project.add_reference("b", "seed")  # b cites seed, stored on b.references, NOT seed.citations
        cites = {p.bib_id for p in project.citations_of("seed")}
        assert cites == {"a"}  # b is not a forward neighbour of seed


def _criterion(id="ic1", name="Peer reviewed", type=CriterionType.inclusion):
    return Criterion(id=id, name=name, type=type)


def _phase(id="title", name="Title screening"):
    return Phase(id=id, name=name)


def _researcher(email="a@b.com", name="Ana"):
    return Researcher(email=email, name=name)


class DescribeCriteria:
    def it_adds_a_criterion(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_criterion(_criterion())
        assert len(project.criteria) == 1
        assert project.criteria[0].id == "ic1"

    def it_rejects_duplicate_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_criterion(_criterion())
        with pytest.raises(ValueError, match="already exists"):
            project.add_criterion(_criterion())

    def it_updates_name_and_type(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_criterion(_criterion())
        project.update_criterion("ic1", name="Updated", type=CriterionType.exclusion)
        c = project.criteria[0]
        assert c.name == "Updated"
        assert c.type == CriterionType.exclusion

    def it_raises_update_for_unknown_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.update_criterion("ghost", name="x", type=CriterionType.inclusion)

    def it_removes_a_criterion(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_criterion(_criterion())
        project.remove_criterion("ic1")
        assert project.criteria == []

    def it_raises_remove_for_unknown_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.remove_criterion("ghost")


class DescribeCriteriaRename:
    def it_renames_criterion_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_criterion(_criterion("ic1"))
        project.rename_criterion("ic1", "ic2")
        assert project.criteria[0].id == "ic2"
        assert not any(c.id == "ic1" for c in project.criteria)

    def it_updates_assessments_on_rename(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_seed(_paper("seed"))
        project.add_criterion(_criterion("ic1"))
        project.add_phase(_phase())
        project.add_researcher(_researcher())
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.rename_criterion("ic1", "ic2")
        assert project.assessments["a@b.com"]["seed"].criterion.id == "ic2"

    def it_rejects_rename_to_existing_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_criterion(_criterion("ic1"))
        project.add_criterion(_criterion("ic2", "Another"))
        with pytest.raises(ValueError, match="already exists"):
            project.rename_criterion("ic1", "ic2")

    def it_raises_rename_for_unknown_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.rename_criterion("ghost", "new")


class DescribePhases:
    def it_adds_a_phase(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_phase(_phase())
        assert len(project.phases) == 1

    def it_rejects_duplicate_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_phase(_phase())
        with pytest.raises(ValueError, match="already exists"):
            project.add_phase(_phase())

    def it_updates_name(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_phase(_phase())
        project.update_phase("title", name="Updated")
        assert project.phases[0].name == "Updated"

    def it_raises_update_for_unknown_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.update_phase("ghost", name="x")

    def it_removes_a_phase(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_phase(_phase())
        project.remove_phase("title")
        assert project.phases == []

    def it_raises_remove_for_unknown_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.remove_phase("ghost")


class DescribePhasesRename:
    def it_renames_phase_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_phase(_phase("title"))
        project.rename_phase("title", "abstract")
        assert project.phases[0].id == "abstract"

    def it_updates_assessments_on_rename(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_seed(_paper("seed"))
        project.add_criterion(_criterion())
        project.add_phase(_phase("title"))
        project.add_researcher(_researcher())
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.rename_phase("title", "abstract")
        assert project.assessments["a@b.com"]["seed"].phase.id == "abstract"

    def it_rejects_rename_to_existing_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_phase(_phase("title"))
        project.add_phase(_phase("abstract", "Abstract screening"))
        with pytest.raises(ValueError, match="already exists"):
            project.rename_phase("title", "abstract")

    def it_raises_rename_for_unknown_id(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.rename_phase("ghost", "new")


class DescribeResearchers:
    def it_adds_a_researcher(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_researcher(_researcher())
        assert len(project.researchers) == 1

    def it_rejects_duplicate_email(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_researcher(_researcher())
        with pytest.raises(ValueError, match="already exists"):
            project.add_researcher(_researcher())

    def it_updates_name(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_researcher(_researcher())
        project.update_researcher("a@b.com", name="Ana Updated")
        assert project.researchers[0].name == "Ana Updated"

    def it_raises_update_for_unknown_email(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.update_researcher("ghost@x.com", name="x")

    def it_removes_a_researcher(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_researcher(_researcher())
        project.remove_researcher("a@b.com")
        assert project.researchers == []

    def it_raises_remove_for_unknown_email(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.remove_researcher("ghost@x.com")


class DescribeResearchersRename:
    def it_renames_researcher_email(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_researcher(_researcher("a@b.com"))
        project.rename_researcher("a@b.com", "new@b.com")
        assert project.researchers[0].email == "new@b.com"

    def it_moves_assessments_on_rename(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_seed(_paper("seed"))
        project.add_criterion(_criterion())
        project.add_phase(_phase())
        project.add_researcher(_researcher("a@b.com"))
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.rename_researcher("a@b.com", "new@b.com")
        assert "new@b.com" in project.assessments
        assert "a@b.com" not in project.assessments

    def it_rejects_rename_to_existing_email(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_researcher(_researcher("a@b.com"))
        project.add_researcher(_researcher("b@b.com", "Bob"))
        with pytest.raises(ValueError, match="already exists"):
            project.rename_researcher("a@b.com", "b@b.com")

    def it_raises_rename_for_unknown_email(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        with pytest.raises(KeyError):
            project.rename_researcher("ghost@x.com", "new@x.com")


class DescribeAssessment:
    def _project_with_review(self, tmp_path):
        project = Project(name="p", path=tmp_path)
        project.add_seed(_paper("seed"))
        project.add_criterion(_criterion("ic1", "Peer reviewed", CriterionType.inclusion))
        project.add_criterion(_criterion("ec1", "Out of scope", CriterionType.exclusion))
        project.add_phase(_phase())
        project.add_researcher(_researcher("a@b.com", "Ana"))
        project.add_researcher(_researcher("b@b.com", "Bob"))
        return project

    def it_records_a_researchers_assessment(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        assert "a@b.com" in project.assessments
        assert "seed" in project.assessments["a@b.com"]

    def it_two_researchers_produce_two_entries(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.assess("seed", criterion_id="ec1", phase_id="title", researcher_email="b@b.com")
        result = project.assessments_of("seed")
        assert set(result.keys()) == {"a@b.com", "b@b.com"}

    def it_overwrites_when_same_researcher_reassesses(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.assess("seed", criterion_id="ec1", phase_id="title", researcher_email="a@b.com")
        assert project.assessments["a@b.com"]["seed"].criterion.id == "ec1"

    def it_derives_included_from_criterion_type(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        assert project.assessments["a@b.com"]["seed"].included is True
        project.assess("seed", criterion_id="ec1", phase_id="title", researcher_email="a@b.com")
        assert project.assessments["a@b.com"]["seed"].included is False

    def it_sets_paper_decision_after_assess(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ec1", phase_id="title", researcher_email="a@b.com")
        assert project.papers["seed"].decision == Decision.excluded

    def it_sets_included_decision_on_inclusion_criterion(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        assert project.papers["seed"].decision == Decision.included

    def it_rejects_unknown_criterion(self, tmp_path):
        project = self._project_with_review(tmp_path)
        with pytest.raises(KeyError):
            project.assess("seed", criterion_id="ghost", phase_id="title", researcher_email="a@b.com")

    def it_rejects_unknown_phase(self, tmp_path):
        project = self._project_with_review(tmp_path)
        with pytest.raises(KeyError):
            project.assess("seed", criterion_id="ic1", phase_id="ghost", researcher_email="a@b.com")

    def it_rejects_unknown_researcher(self, tmp_path):
        project = self._project_with_review(tmp_path)
        with pytest.raises(KeyError):
            project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="ghost@x.com")

    def it_round_trips_assessments_through_save_and_load(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.add_paper(_full_paper("seed"))  # ensure save-able
        # save requires complete papers; use full paper for seed
        project2 = Project(name="p", path=tmp_path)
        project2.add_seed(_full_paper("seed"))
        project2.add_criterion(_criterion("ic1", "Peer reviewed", CriterionType.inclusion))
        project2.add_phase(_phase())
        project2.add_researcher(_researcher("a@b.com", "Ana"))
        project2.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project2.save()
        loaded = Project.load(tmp_path)
        assert "a@b.com" in loaded.assessments
        assert "seed" in loaded.assessments["a@b.com"]
        assert loaded.assessments["a@b.com"]["seed"].criterion.id == "ic1"

    def it_assessments_of_gathers_a_papers_entries(self, tmp_path):
        project = self._project_with_review(tmp_path)
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.assess("seed", criterion_id="ec1", phase_id="title", researcher_email="b@b.com")
        result = project.assessments_of("seed")
        assert isinstance(result, dict)
        assert result["a@b.com"].criterion.id == "ic1"
        assert result["b@b.com"].criterion.id == "ec1"


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
        assert (tmp_path / "sets" / "start_set.yml").exists()
        assert (tmp_path / "sets" / "backward-1.yml").exists()

    def it_writes_name_but_not_seeds_or_paper_sets_in_project_yml(self, tmp_path):
        self._saved_project(tmp_path)
        data = yaml.safe_load((tmp_path / "project.yml").read_text(encoding="utf-8"))
        assert data["name"] == "slr"
        assert "seeds" not in data
        assert "paper_sets" not in data
        assert "path" not in data
        assert "papers" not in data

    def it_writes_seeds_to_start_set_yml(self, tmp_path):
        self._saved_project(tmp_path)
        start_data = yaml.safe_load((tmp_path / "sets" / "start_set.yml").read_text(encoding="utf-8"))
        assert "seed" in start_data["paper_ids"]

    def it_removes_a_set_file_when_it_empties(self, tmp_path):
        project = self._saved_project(tmp_path)
        assert (tmp_path / "sets" / "backward-1.yml").exists()
        # Excluding does not empty a set, but adding a shorter path that moves the
        # only member out of backward-1 should remove the stale file on re-save.
        project.add_citation("seed", "a")  # now a also forward-1; still placed backward-1
        # Re-route: make a a seed's citation only by removing the reference path.
        project.papers["seed"].references.discard("a")
        project._derive()
        project.save()
        assert not (tmp_path / "sets" / "backward-1.yml").exists()
        assert (tmp_path / "sets" / "forward-1.yml").exists()

    def it_round_trips_seeds_edges_decision_and_placement(self, tmp_path):
        project = Project(name="slr", path=tmp_path)
        project.add_seed(_full_paper("seed"))
        for bib_id in ("a", "b", "x"):
            project.add_paper(_full_paper(bib_id))
        project.add_reference("seed", "a")
        project.add_reference("a", "x")
        project.add_reference("seed", "b")
        project.add_criterion(_criterion("ec1", "Out of scope", CriterionType.exclusion))
        project.add_phase(_phase())
        project.add_researcher(_researcher())
        project.assess("b", criterion_id="ec1", phase_id="title", researcher_email="a@b.com")
        assert project.papers["b"].decision == Decision.excluded
        project.save()

        loaded = Project.load(tmp_path)
        assert loaded.name == project.name
        assert loaded.seeds == project.seeds
        assert loaded.papers["seed"].references == {"a", "b"}
        assert loaded.papers["b"].decision == Decision.excluded
        assert loaded.set_of("seed") == "start_set"
        assert loaded.set_of("a") == "backward-1"
        assert loaded.set_of("x") == "backward-2"
        assert loaded.set_of("b") == "backward-1"

    def it_recomputes_decisions_when_strategy_changes(self, tmp_path):
        project = Project(name="slr", path=tmp_path)
        project.add_seed(_full_paper("seed"))
        project.add_criterion(_criterion("ic1", "Peer reviewed", CriterionType.inclusion))
        project.add_criterion(_criterion("ec1", "Out of scope", CriterionType.exclusion))
        project.add_phase(_phase())
        project.add_researcher(_researcher("a@b.com", "Ana"))
        project.add_researcher(_researcher("b@b.com", "Bob"))
        # one inclusion, one exclusion — majority → undecided; consensus → undecided
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="a@b.com")
        project.assess("seed", criterion_id="ec1", phase_id="title", researcher_email="b@b.com")
        assert project.papers["seed"].decision == Decision.undecided
        # switching strategy shouldn't change a tie under either algorithm
        project.set_decision_strategy(DecisionStrategyType.consensus)
        assert project.papers["seed"].decision == Decision.undecided
        # unanimous inclusion under consensus → included
        project.assess("seed", criterion_id="ic1", phase_id="title", researcher_email="b@b.com")
        assert project.papers["seed"].decision == Decision.included
