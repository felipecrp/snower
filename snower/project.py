from collections import defaultdict, deque
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

    A set's identity is its `name` (the direction: ``start`` / ``backward`` /
    ``forward`` / ``orphan``) together with its `round`. It holds bib_id
    references into the project's canonical paper map rather than paper contents,
    so resolving members never duplicates a paper.

    Sets are a *projection* of the project's derived placement, materialised for
    the public API and for persistence; they are not the source of truth.
    """

    name: str
    round: int
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
    *derived* from the graph by snowballing outward from the seeds — see
    `doc/snowballing.md`.

    Set membership lives in the private `_placement` index, kept live and updated
    incrementally by the four mutators (`add_reference`, `add_citation`,
    `include`, `exclude`). Papers with no included path back to a seed are absent
    from `_placement` and reported as the ``orphan`` set, round ``-1``.
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
        self._placement[paper.bib_id] = ("start", 0)
        self._propagate([paper.bib_id])

    # ----- edge mutators ------------------------------------------------

    def add_reference(self, citing_id: str, cited_id: str) -> None:
        """Record that ``citing_id`` cites ``cited_id`` (backward edge) and re-derive.

        Raises KeyError if either paper is unknown and ValueError on self-citation.
        """
        self._require_edge(citing_id, cited_id)
        self.papers[citing_id].add_reference(cited_id)
        self._relax_edge(citing_id, cited_id)

    def add_citation(self, cited_id: str, citing_id: str) -> None:
        """Record that ``citing_id`` cites ``cited_id`` (forward edge) and re-derive.

        Stores the same directed edge as the equivalent
        ``add_reference(citing_id, cited_id)``, only on the citations side.
        Raises KeyError if either paper is unknown and ValueError on self-citation.
        """
        self._require_edge(citing_id, cited_id)
        self.papers[cited_id].add_citation(citing_id)
        self._relax_edge(citing_id, cited_id)

    def _require_edge(self, citing_id: str, cited_id: str) -> None:
        """Validate an edge's endpoints: both must exist and must differ."""
        for bib_id in (citing_id, cited_id):
            if bib_id not in self.papers:
                raise KeyError(f"Unknown paper {bib_id!r}")
        if citing_id == cited_id:
            raise ValueError(f"A paper cannot cite itself: {citing_id!r}")

    # ----- screening ----------------------------------------------------

    def include(self, bib_id: str) -> None:
        """Mark a paper included again and let it propagate placement to neighbours.

        The paper keeps its own placement; including it merely re-enables its
        outward contribution, so dependents that orphaned (or sat at a higher
        round) when it was excluded are re-derived.
        """
        self.papers[bib_id].included = True
        self._propagate([bib_id])

    def exclude(self, bib_id: str) -> None:
        """Mark a paper excluded: it keeps its set but stops propagating.

        Its dependents re-derive through other included parents, or become
        orphans. Implemented by re-deriving placement from the seeds — exclude is
        the rare, subtle case (equal-length alternative paths), so a full
        re-derivation is both correct and simplest.
        """
        self.papers[bib_id].included = False
        self._rederive()

    # ----- placement core ----------------------------------------------

    def _relax_edge(self, citing_id: str, cited_id: str) -> None:
        """Relax placement across a newly added ``citing -> cited`` edge.

        Edge-adds can only ever *lower* a round, so a decrease-only cascade from
        both endpoints suffices: a placed, included ``citing`` offers ``cited`` a
        backward placement, and a placed, included ``cited`` offers ``citing`` a
        forward placement; improvements ripple outward and terminate quickly.
        """
        self._propagate([citing_id, cited_id])

    def _propagate(self, sources: list[str]) -> None:
        """Relax placement outward from `sources` until nothing improves.

        Each placed, *included* paper offers every backward neighbour a
        ``(backward, round + 1)`` placement and every forward neighbour a
        ``(forward, round + 1)`` placement. A paper that improves is re-enqueued so
        the improvement cascades. Excluded papers may receive a placement but never
        offer one (rule 4). Rounds only decrease, so the worklist terminates.
        """
        rev_references, rev_citations = self._reverse_index()
        queue = deque(sources)
        while queue:
            pid = queue.popleft()
            placement = self._placement.get(pid)
            if placement is None or not self.papers[pid].included:
                continue
            next_round = placement[1] + 1
            for neighbour in self._backward_neighbours(pid, rev_citations):
                if self._improve(neighbour, ("backward", next_round)):
                    queue.append(neighbour)
            for neighbour in self._forward_neighbours(pid, rev_references):
                if self._improve(neighbour, ("forward", next_round)):
                    queue.append(neighbour)

    def _rederive(self) -> None:
        """Rebuild `_placement` from scratch by snowballing from the seeds.

        A one-time multi-source traversal: the only place a full graph walk runs.
        Used by `exclude` and by `load`, where incremental updates do not apply.
        """
        self._placement = {s: ("start", 0) for s in self.seeds if s in self.papers}
        self._propagate(list(self._placement))

    def _improve(self, bib_id: str, candidate: Placement) -> bool:
        """Apply `candidate` to `bib_id` if it is better; return whether to re-propagate.

        Returns True only when the *round* strictly improved (a brand-new
        placement or a lower round), since that is what changes neighbours. A
        same-round backward-over-forward upgrade is applied but does not need to
        re-propagate: a neighbour's round depends on the edge to it, not on this
        paper's direction.
        """
        current = self._placement.get(bib_id)
        if not self._is_better(candidate, current):
            return False
        self._placement[bib_id] = candidate
        return current is None or candidate[1] < current[1]

    @staticmethod
    def _is_better(candidate: Placement, current: Placement | None) -> bool:
        """Return whether `candidate` should replace `current` (lower round, or
        equal round with backward beating forward; rule 6)."""
        if current is None:
            return True
        if candidate[1] != current[1]:
            return candidate[1] < current[1]
        return candidate[0] == "backward" and current[0] == "forward"

    # ----- runtime reverse index ----------------------------------------

    def _reverse_index(self) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Build the runtime reverse adjacency once for the current mutation.

        Because each edge is stored on only one side, full neighbours need a scan
        of the opposite side. Returns ``(rev_references, rev_citations)`` where
        ``rev_references[x] = {p : x ∈ p.references}`` and
        ``rev_citations[x] = {p : x ∈ p.citations}``.
        """
        rev_references: dict[str, set[str]] = defaultdict(set)
        rev_citations: dict[str, set[str]] = defaultdict(set)
        for pid, paper in self.papers.items():
            for cited in paper.references:
                rev_references[cited].add(pid)
            for citing in paper.citations:
                rev_citations[citing].add(pid)
        return rev_references, rev_citations

    def _backward_neighbours(self, bib_id: str, rev_citations: dict[str, set[str]]) -> set[str]:
        """All papers ``bib_id`` cites (its references), from both stored sides."""
        return self.papers[bib_id].references | rev_citations.get(bib_id, set())

    def _forward_neighbours(self, bib_id: str, rev_references: dict[str, set[str]]) -> set[str]:
        """All papers that cite ``bib_id`` (its citations), from both stored sides."""
        return self.papers[bib_id].citations | rev_references.get(bib_id, set())

    # ----- read accessors -----------------------------------------------

    def set_of(self, bib_id: str) -> str:
        """Return the ``{direction}-{round}`` name of the set holding `bib_id`.

        Unplaced papers report the orphan set, ``"orphan--1"``.
        """
        direction, round_ = self._placement.get(bib_id, self._ORPHAN)
        return f"{direction}-{round_}"

    def papers_in(self, set_name: str) -> list[Paper]:
        """Return the Paper objects currently belonging to the named set."""
        return [self.papers[bib_id] for bib_id in self.papers if self.set_of(bib_id) == set_name]

    def references_of(self, bib_id: str) -> list[Paper]:
        """Return the Paper objects this paper cites (full backward neighbours)."""
        _, rev_citations = self._reverse_index()
        return [
            self.papers[n]
            for n in self._backward_neighbours(bib_id, rev_citations)
            if n in self.papers
        ]

    def citations_of(self, bib_id: str) -> list[Paper]:
        """Return the Paper objects that cite this paper (full forward neighbours)."""
        rev_references, _ = self._reverse_index()
        return [
            self.papers[n]
            for n in self._forward_neighbours(bib_id, rev_references)
            if n in self.papers
        ]

    # ----- set projection & persistence ---------------------------------

    def _build_sets(self) -> list[PaperSet]:
        """Materialise the current placement as a list of `PaperSet` projections."""
        sets: dict[Placement, PaperSet] = {}
        for bib_id in self.papers:
            direction, round_ = self._placement.get(bib_id, self._ORPHAN)
            paper_set = sets.get((direction, round_))
            if paper_set is None:
                paper_set = PaperSet(name=direction, round=round_)
                sets[(direction, round_)] = paper_set
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
        project._rederive()
        return project
