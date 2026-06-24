from pathlib import Path
from typing import ClassVar

import yaml
from pydantic import BaseModel, PrivateAttr

from snower.paper import Paper
from snower.repository import PaperRepository, SetRepository

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

    _METADATA_FILE: ClassVar[str] = "project.yml"
    _PAPERS_DIR: ClassVar[str] = "papers"
    _SETS_DIR: ClassVar[str] = "sets"
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

    # ----- screening ----------------------------------------------------

    def include(self, bib_id: str) -> None:
        """Mark a paper included again and re-derive placement from the seeds.

        Including re-enables the paper's outward contribution, so dependents that
        orphaned (or sat at a higher round) when it was excluded are rerouted.
        """
        self.papers[bib_id].included = True
        self._derive()

    def exclude(self, bib_id: str) -> None:
        """Mark a paper excluded: it keeps its set but stops propagating.

        Its dependents re-derive through other included parents, or become orphans.
        """
        self.papers[bib_id].included = False
        self._derive()

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
                    if not self.papers[member].included:
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
        metadata = self.model_dump(mode="json", exclude={"path", "papers"})
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
        seeds = set(metadata.get("seeds", []))
        project = cls(name=metadata["name"], path=path, papers=papers, seeds=seeds)
        project._derive()
        return project
