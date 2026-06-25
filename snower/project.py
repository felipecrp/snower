from pathlib import Path
from typing import ClassVar

import yaml
from pydantic import BaseModel, PrivateAttr

from snower.decision import Decision, DecisionStrategyType, strategy_for
from snower.paper import Paper
from snower.repository import PaperRepository, ReviewRepository, SetRepository
from snower.review import Assessment, Criterion, CriterionType, Phase, Researcher

# A placement is (direction, round). Directions are ordered for tie-breaking:
# at equal round, "backward" beats "forward" (rule 6). Seeds sit at ("start", 0).
Placement = tuple[str, int]


class PaperSet(BaseModel):
    """A named set of papers belonging to one snowballing round and direction.

    A set's identity is its `name`. For directional sets (``backward`` /
    ``forward``) `round` is the BFS depth; for the seed set (``start_set``) and
    unplaced papers (``orphans``) `round` is ``None`` because round is not
    meaningful. It holds bib_id references into the project's canonical paper
    map rather than paper contents, so resolving members never duplicates a paper.

    Sets are a *projection* of the project's derived placement, materialised for
    the public API and for persistence; they are not the source of truth.
    """

    name: str
    round: int | None
    paper_ids: set[str] = set()

    def add(self, bib_id: str) -> None:
        """Add bib_id to this set."""
        self.paper_ids.add(bib_id)

    def remove(self, bib_id: str) -> None:
        """Remove bib_id from this set; no-op if it is not present."""
        self.paper_ids.discard(bib_id)


class Project(BaseModel):
    """A snowballing project: a citation graph whose set membership is derived.

    Papers are stored exactly once in `papers` (keyed by bib_id) and double as the
    nodes of the citation graph. `seeds` are the bib_ids that anchor the review at
    round 0. Every other paper's set (a backward/forward direction and a round) is
    *derived* from the graph by a single layered BFS from the seeds — see
    `doc/snowballing.md`.

    Set membership lives in the private `_placement` index, rebuilt from scratch by
    `_derive()` after every mutation. Papers with no included path back to a seed
    are absent from `_placement` and reported as the ``orphan`` set, round ``-1``.
    """

    name: str
    path: Path
    papers: dict[str, Paper] = {}
    seeds: set[str] = set()
    criteria: list[Criterion] = []
    phases: list[Phase] = []
    researchers: list[Researcher] = []
    # researcher_email -> { bib_id -> latest Assessment }
    assessments: dict[str, dict[str, Assessment]] = {}
    decision_strategy: DecisionStrategyType = DecisionStrategyType.majority

    _METADATA_FILE: ClassVar[str] = "project.yml"
    _PAPERS_DIR: ClassVar[str] = "papers"
    _SETS_DIR: ClassVar[str] = "sets"
    _REVIEW_DIR: ClassVar[str] = "review"
    _ORPHAN: ClassVar[Placement] = ("orphan", -1)

    # Derived set membership: bib_id -> (direction, round). Seeds map to
    # ("start", 0); orphans are simply absent.
    _placement: dict[str, Placement] = PrivateAttr(default_factory=dict)

    # ----- registration -------------------------------------------------

    def add_paper(self, paper: Paper) -> None:
        """Register a paper in the canonical map under its bib_id.

        The paper enters as an orphan; it only gains a set once an edge connects
        it to a seed. Raises ValueError if the paper has no bib_id.
        """
        if not paper.bib_id:
            raise ValueError("Paper must have a bib_id to be added to a project")
        self.papers[paper.bib_id] = paper

    def add_seed(self, paper: Paper) -> None:
        """Register a paper as a seed, placing it at ``start-0`` and snowballing out.

        Raises ValueError if the paper has no bib_id.
        """
        self.add_paper(paper)
        self.seeds.add(paper.bib_id)
        self._derive()

    def remove_seed(self, bib_id: str) -> None:
        """Remove a paper from seeds and re-derive placement.

        The paper stays in the project; it will be re-placed as an orphan or via other
        graph paths. Raises KeyError if bib_id is not currently a seed.
        """
        if bib_id not in self.seeds:
            raise KeyError(f"{bib_id!r} is not a seed")
        self.seeds.discard(bib_id)
        self._derive()

    # ----- edge mutators ------------------------------------------------

    def add_reference(self, citing_id: str, cited_id: str) -> None:
        """Record that ``citing_id`` cites ``cited_id`` (backward edge) and re-derive.

        Raises KeyError if either paper is unknown and ValueError on self-citation.
        """
        self._require_edge(citing_id, cited_id)
        self.papers[citing_id].add_reference(cited_id)
        self._derive()

    def add_citation(self, cited_id: str, citing_id: str) -> None:
        """Record that ``citing_id`` cites ``cited_id`` (forward edge) and re-derive.

        Stores the edge on the cited paper's ``citations`` set (the forward side).
        Raises KeyError if either paper is unknown and ValueError on self-citation.
        """
        self._require_edge(citing_id, cited_id)
        self.papers[cited_id].add_citation(citing_id)
        self._derive()

    def _require_edge(self, citing_id: str, cited_id: str) -> None:
        """Validate an edge's endpoints: both must exist and must differ."""
        for bib_id in (citing_id, cited_id):
            if bib_id not in self.papers:
                raise KeyError(f"Unknown paper {bib_id!r}")
        if citing_id == cited_id:
            raise ValueError(f"A paper cannot cite itself: {citing_id!r}")

    # ----- criteria -------------------------------------------------------

    def add_criterion(self, criterion: Criterion) -> None:
        """Append a criterion, raising ValueError on duplicate id."""
        if any(c.id == criterion.id for c in self.criteria):
            raise ValueError(f"Criterion {criterion.id!r} already exists")
        self.criteria.append(criterion)

    def _require_criterion(self, id: str) -> Criterion:
        """Return the criterion with the given id, or raise KeyError."""
        for c in self.criteria:
            if c.id == id:
                return c
        raise KeyError(f"Unknown criterion {id!r}")

    def update_criterion(self, id: str, *, name: str, type: CriterionType) -> None:
        """Replace a criterion's mutable fields in place, keyed by its immutable id."""
        c = self._require_criterion(id)
        c.name = name
        c.type = type

    def remove_criterion(self, id: str) -> None:
        """Remove the criterion with the given id, raising KeyError if absent."""
        self._require_criterion(id)
        self.criteria = [c for c in self.criteria if c.id != id]

    def rename_criterion(self, old_id: str, new_id: str) -> None:
        """Rename a criterion's id, updating all assessments that reference it.

        Raises KeyError if old_id is unknown, ValueError if new_id already exists.
        """
        if any(c.id == new_id for c in self.criteria):
            raise ValueError(f"Criterion {new_id!r} already exists")
        c = self._require_criterion(old_id)
        c.id = new_id
        for papers in self.assessments.values():
            for assessment in papers.values():
                if assessment.criterion.id == old_id:
                    assessment.criterion.id = new_id

    # ----- phases ---------------------------------------------------------

    def add_phase(self, phase: Phase) -> None:
        """Append a phase, raising ValueError on duplicate id."""
        if any(p.id == phase.id for p in self.phases):
            raise ValueError(f"Phase {phase.id!r} already exists")
        self.phases.append(phase)

    def _require_phase(self, id: str) -> Phase:
        """Return the phase with the given id, or raise KeyError."""
        for p in self.phases:
            if p.id == id:
                return p
        raise KeyError(f"Unknown phase {id!r}")

    def update_phase(self, id: str, *, name: str) -> None:
        """Replace a phase's mutable fields in place, keyed by its immutable id."""
        p = self._require_phase(id)
        p.name = name

    def remove_phase(self, id: str) -> None:
        """Remove the phase with the given id, raising KeyError if absent."""
        self._require_phase(id)
        self.phases = [p for p in self.phases if p.id != id]

    def rename_phase(self, old_id: str, new_id: str) -> None:
        """Rename a phase's id, updating all assessments that reference it.

        Raises KeyError if old_id is unknown, ValueError if new_id already exists.
        """
        if any(p.id == new_id for p in self.phases):
            raise ValueError(f"Phase {new_id!r} already exists")
        p = self._require_phase(old_id)
        p.id = new_id
        for papers in self.assessments.values():
            for assessment in papers.values():
                if assessment.phase.id == old_id:
                    assessment.phase.id = new_id

    # ----- researchers ----------------------------------------------------

    def add_researcher(self, researcher: Researcher) -> None:
        """Append a researcher, raising ValueError on duplicate email."""
        if any(r.email == researcher.email for r in self.researchers):
            raise ValueError(f"Researcher {researcher.email!r} already exists")
        self.researchers.append(researcher)

    def _require_researcher(self, email: str) -> Researcher:
        """Return the researcher with the given email, or raise KeyError."""
        for r in self.researchers:
            if r.email == email:
                return r
        raise KeyError(f"Unknown researcher {email!r}")

    def update_researcher(self, email: str, *, name: str) -> None:
        """Replace a researcher's mutable fields in place, keyed by email."""
        r = self._require_researcher(email)
        r.name = name

    def remove_researcher(self, email: str) -> None:
        """Remove the researcher with the given email, raising KeyError if absent."""
        self._require_researcher(email)
        self.researchers = [r for r in self.researchers if r.email != email]

    def rename_researcher(self, old_email: str, new_email: str) -> None:
        """Rename a researcher's email, moving their assessments to the new key.

        Raises KeyError if old_email is unknown, ValueError if new_email already exists.
        """
        if any(r.email == new_email for r in self.researchers):
            raise ValueError(f"Researcher {new_email!r} already exists")
        r = self._require_researcher(old_email)
        r.email = new_email
        if old_email in self.assessments:
            self.assessments[new_email] = self.assessments.pop(old_email)

    # ----- assessments ----------------------------------------------------

    def assess(
        self,
        bib_id: str,
        *,
        criterion_id: str,
        phase_id: str,
        researcher_email: str,
        comment: str | None = None,
    ) -> None:
        """Record a researcher's screening opinion for a paper.

        Resolves criterion_id and phase_id to the project's objects (KeyError if
        unknown), validates the researcher, then stores or overwrites that
        researcher's latest Assessment for the paper. Recomputes the paper's
        decision from all its reviews using the project's decision strategy, then
        re-derives snowball placement.
        """
        criterion = self._require_criterion(criterion_id)
        phase = self._require_phase(phase_id)
        self._require_researcher(researcher_email)
        if bib_id not in self.papers:
            raise KeyError(f"Unknown paper {bib_id!r}")
        self.assessments.setdefault(researcher_email, {})[bib_id] = Assessment(
            criterion=criterion, phase=phase, comment=comment or None
        )
        self.papers[bib_id].decision = strategy_for(self.decision_strategy).decide(
            self.assessments_of(bib_id).values()
        )
        self._derive()

    def remove_assessment(self, bib_id: str, researcher_email: str) -> None:
        """Remove a researcher's assessment for a paper and recompute its decision.

        Raises KeyError if the paper, researcher, or assessment is not found.
        Re-derives snowball placement after updating the decision.
        """
        self._require_researcher(researcher_email)
        if bib_id not in self.papers:
            raise KeyError(f"Unknown paper {bib_id!r}")
        if researcher_email not in self.assessments or bib_id not in self.assessments[researcher_email]:
            raise KeyError(f"No assessment for {researcher_email!r} on {bib_id!r}")
        del self.assessments[researcher_email][bib_id]
        self.papers[bib_id].decision = strategy_for(self.decision_strategy).decide(
            self.assessments_of(bib_id).values()
        )
        self._derive()

    def assessments_of(self, bib_id: str) -> dict[str, Assessment]:
        """Gather a paper's assessments across all researchers (email → Assessment)."""
        return {
            email: papers[bib_id]
            for email, papers in self.assessments.items()
            if bib_id in papers
        }

    # ----- screening ----------------------------------------------------

    def include(self, bib_id: str) -> None:
        """Manually set a paper's decision to included and re-derive placement.

        Including re-enables the paper's outward contribution, so dependents that
        orphaned (or sat at a higher round) when it was excluded are rerouted.
        Note: this decision is overwritten by `_decide_all()` on reload or
        strategy change.
        """
        self.papers[bib_id].decision = Decision.included
        self._derive()

    def exclude(self, bib_id: str) -> None:
        """Manually set a paper's decision to excluded: it keeps its set but stops propagating.

        Its dependents re-derive through other included parents, or become orphans.
        Note: this decision is overwritten by `_decide_all()` on reload or
        strategy change.
        """
        self.papers[bib_id].decision = Decision.excluded
        self._derive()

    def set_decision_strategy(self, type: DecisionStrategyType) -> None:
        """Switch the decision strategy and recompute every paper's decision.

        Switching strategy calls `_decide_all()` (recomputes every paper's decision
        from its reviews) then `_derive()` (rebuilds snowball placement).
        """
        self.decision_strategy = type
        self._decide_all()
        self._derive()

    def _decide_all(self) -> None:
        """Recompute every paper's decision from its reviews and the current strategy."""
        strategy = strategy_for(self.decision_strategy)
        for bib_id, paper in self.papers.items():
            paper.decision = strategy.decide(self.assessments_of(bib_id).values())

    # ----- placement core ----------------------------------------------

    def _derive(self) -> None:
        """Rebuild `_placement` from seeds via a single layered BFS.

        Each BFS layer is one round. Within a round, the backward pass runs across
        the whole frontier before the forward pass, so backward wins a same-round
        tie (rule 6). An already-placed paper reached again is skipped. Excluded
        papers receive a placement but do not propagate to their neighbours (rule 4).
        """
        placement: dict[str, Placement] = {s: ("start", 0) for s in self.seeds if s in self.papers}
        frontier = list(placement)
        round_ = 0
        while frontier:
            round_ += 1
            next_frontier: list[str] = []
            for direction, attr in [("backward", "references"), ("forward", "citations")]:
                for member in frontier:
                    if self.papers[member].decision is Decision.excluded:
                        continue
                    for nb in getattr(self.papers[member], attr):
                        if nb not in self.papers or nb in placement:
                            continue
                        placement[nb] = (direction, round_)
                        next_frontier.append(nb)
            frontier = next_frontier
        self._placement = placement

    # ----- read accessors -----------------------------------------------

    _SET_NAMES: ClassVar[dict[tuple[str, int], str]] = {
        ("start", 0): "start_set",
        ("orphan", -1): "orphans",
    }

    def set_of(self, bib_id: str) -> str:
        """Return the canonical set name for `bib_id`.

        Seeds → ``"start_set"``; unplaced papers → ``"orphans"``; derived
        papers → ``"{direction}-{round}"``.
        """
        placement = self._placement.get(bib_id, self._ORPHAN)
        if placement in self._SET_NAMES:
            return self._SET_NAMES[placement]
        direction, round_ = placement
        return f"{direction}-{round_}"

    def papers_in(self, set_name: str) -> list[Paper]:
        """Return the Paper objects currently belonging to the named set."""
        return [self.papers[bib_id] for bib_id in self.papers if self.set_of(bib_id) == set_name]

    def references_of(self, bib_id: str) -> list[Paper]:
        """Return the Paper objects this paper cites (backward neighbours, from references only)."""
        return [self.papers[n] for n in self.papers[bib_id].references if n in self.papers]

    def citations_of(self, bib_id: str) -> list[Paper]:
        """Return the Paper objects that cite this paper (forward neighbours, from citations only)."""
        return [self.papers[n] for n in self.papers[bib_id].citations if n in self.papers]

    # ----- set projection & persistence ---------------------------------

    def sets(self) -> list[PaperSet]:
        """Return the current set projections derived from the placement index."""
        return self._build_sets()

    def _build_sets(self) -> list[PaperSet]:
        """Materialise the current placement as a list of `PaperSet` projections."""
        sets: dict[str, PaperSet] = {}
        for bib_id in self.papers:
            placement = self._placement.get(bib_id, self._ORPHAN)
            special_name = self._SET_NAMES.get(placement)
            if special_name is not None:
                key = special_name
                name: str = special_name
                round_: int | None = None
            else:
                direction, r = placement
                key = f"{direction}-{r}"
                name = direction
                round_ = r
            paper_set = sets.get(key)
            if paper_set is None:
                paper_set = PaperSet(name=name, round=round_)
                sets[key] = paper_set
            paper_set.add(bib_id)
        return list(sets.values())

    def save(self) -> Path:
        """Persist the project to disk.

        Writes each paper to `papers/` via PaperRepository, the materialised set
        projection to `sets/` via SetRepository (cleared first, so emptied sets
        leave no stale file), and `name` + `seeds` to `project.yml`. Returns the
        project directory.
        """
        self.path.mkdir(parents=True, exist_ok=True)
        paper_repo = PaperRepository(self.path / self._PAPERS_DIR)
        for paper in self.papers.values():
            paper_repo.save(paper)
        SetRepository(self.path / self._SETS_DIR).save_all(self._build_sets())
        ReviewRepository(self.path / self._REVIEW_DIR).save_all(self.assessments)
        metadata = self.model_dump(mode="json", exclude={"path", "papers", "assessments", "seeds"})
        (self.path / self._METADATA_FILE).write_text(
            yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return self.path

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        """Load a project from disk and re-derive its placement from the graph.

        Reads `project.yml` for name and seeds, loads all papers from `papers/`,
        then snowballs from the seeds to rebuild placement. The `sets/` files are a
        materialised snapshot only, so they can never drift from the graph. Raises
        FileNotFoundError if `project.yml` is absent.
        """
        path = Path(path)
        metadata = yaml.safe_load((path / cls._METADATA_FILE).read_text(encoding="utf-8"))
        papers_dir = path / cls._PAPERS_DIR
        paper_list = PaperRepository(papers_dir).load_all() if papers_dir.exists() else []
        papers = {p.bib_id: p for p in paper_list}
        start_set_path = path / cls._SETS_DIR / "start_set.yml"
        if start_set_path.exists():
            start_data = yaml.safe_load(start_set_path.read_text(encoding="utf-8"))
            seeds = set(start_data.get("paper_ids", []))
        else:
            seeds = set(metadata.get("seeds", []))
        criteria = [Criterion(**c) for c in metadata.get("criteria", [])]
        phases = [Phase(**p) for p in metadata.get("phases", [])]
        researchers = [Researcher(**r) for r in metadata.get("researchers", [])]
        review_dir = path / cls._REVIEW_DIR
        assessments = (
            ReviewRepository(review_dir).load_all(criteria=criteria, phases=phases)
            if review_dir.exists()
            else {}
        )
        decision_strategy = DecisionStrategyType(
            metadata.get("decision_strategy", DecisionStrategyType.majority.value)
        )
        project = cls(
            name=metadata["name"],
            path=path,
            papers=papers,
            seeds=seeds,
            criteria=criteria,
            phases=phases,
            researchers=researchers,
            assessments=assessments,
            decision_strategy=decision_strategy,
        )
        project._decide_all()
        project._derive()
        return project
