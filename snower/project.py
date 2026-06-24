from pathlib import Path
from typing import ClassVar

import yaml
from pydantic import BaseModel, PrivateAttr

from snower.paper import Paper
from snower.repository import PaperRepository


class PaperSet(BaseModel):
    """A named set of papers belonging to one snowballing round.

    Holds bib_id references into the project's canonical paper map rather than
    paper contents, so a paper can appear in multiple sets without duplication.
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
    """A snowballing project: a named workspace with a canonical paper map and named paper sets.

    Papers are stored exactly once in `papers` (keyed by bib_id); sets reference
    them by id so a paper can belong to several rounds without duplication.
    """

    name: str
    path: Path
    papers: dict[str, Paper] = {}
    paper_sets: dict[str, PaperSet] = {}

    _METADATA_FILE: ClassVar[str] = "project.yml"
    _PAPERS_DIR: ClassVar[str] = "papers"
    _paper_set_index: dict[str, str] = PrivateAttr(default_factory=dict)

    def add_paper(self, paper: Paper) -> None:
        """Store paper in the canonical map under its bib_id.

        Raises ValueError if the paper has no bib_id.
        """
        if not paper.bib_id:
            raise ValueError("Paper must have a bib_id to be added to a project")
        self.papers[paper.bib_id] = paper

    def add_set(self, name: str, round: int) -> PaperSet:
        """Create and register a new empty PaperSet, or return the existing one."""
        if name not in self.paper_sets:
            self.paper_sets[name] = PaperSet(name=name, round=round)
        return self.paper_sets[name]

    def set_of(self, bib_id: str) -> str | None:
        """Return the name of the set containing bib_id, or None if it belongs to no set."""
        return self._paper_set_index.get(bib_id)

    def add_to_set(self, set_name: str, paper: Paper) -> None:
        """Add paper to the canonical map and append its bib_id to the named set.

        A paper may belong to at most one set. Re-adding it to the set it already
        belongs to is a no-op; adding it while it belongs to a different set raises
        ValueError (use ``move_to_set`` to relocate it instead).

        Raises KeyError if set_name does not exist.
        """
        if set_name not in self.paper_sets:
            raise KeyError(f"Paper set {set_name!r} does not exist")
        self.add_paper(paper)
        current = self._paper_set_index.get(paper.bib_id)
        if current is not None and current != set_name:
            raise ValueError(
                f"Paper {paper.bib_id!r} already belongs to set {current!r}; "
                f"use move_to_set to relocate it"
            )
        self.paper_sets[set_name].add(paper.bib_id)
        self._paper_set_index[paper.bib_id] = set_name

    def move_to_set(self, set_name: str, paper: Paper) -> None:
        """Move paper into the named set, removing it from any set it currently belongs to.

        Adds the paper to the canonical map if absent. Moving a paper into the set
        it already belongs to is a no-op.

        Raises KeyError if set_name does not exist.
        """
        if set_name not in self.paper_sets:
            raise KeyError(f"Paper set {set_name!r} does not exist")
        self.add_paper(paper)
        current = self._paper_set_index.get(paper.bib_id)
        if current is not None:
            self.paper_sets[current].remove(paper.bib_id)
        self.paper_sets[set_name].add(paper.bib_id)
        self._paper_set_index[paper.bib_id] = set_name

    def papers_in(self, set_name: str) -> list[Paper]:
        """Return the Paper objects belonging to the named set."""
        return [self.papers[bib_id] for bib_id in self.paper_sets[set_name].paper_ids]

    def save(self) -> Path:
        """Persist the project to disk.

        Writes each paper to `papers/` via PaperRepository and writes
        name + paper_sets to `project.yml`. Returns the project directory.
        """
        self.path.mkdir(parents=True, exist_ok=True)
        repo = PaperRepository(self.path / self._PAPERS_DIR)
        for paper in self.papers.values():
            repo.save(paper)
        metadata = self.model_dump(mode="json", exclude={"path", "papers"})
        (self.path / self._METADATA_FILE).write_text(
            yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return self.path

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        """Load a project from disk.

        Reads `project.yml` for name and paper_sets, then loads all papers
        from the `papers/` subdirectory. Raises FileNotFoundError if
        `project.yml` is absent.
        """
        path = Path(path)
        metadata = yaml.safe_load((path / cls._METADATA_FILE).read_text(encoding="utf-8"))
        papers_dir = path / cls._PAPERS_DIR
        if papers_dir.exists():
            paper_list = PaperRepository(papers_dir).load_all()
        else:
            paper_list = []
        papers = {p.bib_id: p for p in paper_list}
        paper_sets = {
            name: PaperSet.model_validate(data)
            for name, data in metadata.get("paper_sets", {}).items()
        }
        project = cls(name=metadata["name"], path=path, papers=papers, paper_sets=paper_sets)
        for set_name, paper_set in paper_sets.items():
            for bib_id in paper_set.paper_ids:
                project._paper_set_index[bib_id] = set_name
        return project
