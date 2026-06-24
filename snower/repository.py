from pathlib import Path

import yaml

from snower.paper import Paper


class PaperRepository:
    """File-backed store of Paper instances, one YAML file per paper
    named `{bib_id}.yml` under a base directory."""

    def __init__(self, directory: str | Path) -> None:
        """Initialise with the path to the storage directory."""
        self.directory = Path(directory)

    def _require_complete(self, paper: Paper) -> None:
        """Raise ValueError listing which required fields are missing."""
        missing = []
        if not paper.bib_id:
            missing.append("bib_id")
        if not paper.authors:
            missing.append("authors")
        if not paper.title:
            missing.append("title")
        if paper.year is None:
            missing.append("year")
        if missing:
            raise ValueError(f"Paper is missing required fields: {', '.join(missing)}")

    def save(self, paper: Paper) -> Path:
        """Validate completeness, then write the paper to `{directory}/{bib_id}.yml`.

        Creates the directory if needed. Raises ValueError if bib_id,
        authors, title, or year is missing.
        """
        self._require_complete(paper)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{paper.bib_id}.yml"
        path.write_text(
            yaml.safe_dump(paper.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    def load(self, bib_id: str) -> Paper:
        """Read `{directory}/{bib_id}.yml` and return a Paper.

        Raises FileNotFoundError if the file does not exist.
        """
        path = self.directory / f"{bib_id}.yml"
        return Paper.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def load_all(self) -> list[Paper]:
        """Load every `*.yml` file in the directory as Paper instances."""
        return [
            Paper.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
            for p in sorted(self.directory.glob("*.yml"))
        ]


class SetRepository:
    """File-backed store of PaperSet projections, one YAML file per set named
    `{escaped_name}-{round}.yml` (spaces in the name become `_`) under a base
    directory.

    These files are a materialised snapshot of a project's derived placement,
    rewritten in full on every save; the graph remains the source of truth.
    """

    def __init__(self, directory: str | Path) -> None:
        """Initialise with the path to the storage directory."""
        self.directory = Path(directory)

    @staticmethod
    def _filename(paper_set) -> str:
        """Return the YAML file name for a set: `{escaped_name}-{round}.yml`."""
        escaped = paper_set.name.replace(" ", "_")
        return f"{escaped}-{paper_set.round}.yml"

    def save(self, paper_set) -> Path:
        """Write a single PaperSet to `{directory}/{escaped_name}-{round}.yml`.

        Creates the directory if needed.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / self._filename(paper_set)
        path.write_text(
            yaml.safe_dump(paper_set.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    def save_all(self, paper_sets) -> None:
        """Replace the directory's contents with `paper_sets`.

        Clears every existing `*.yml` first so a set that became empty leaves no
        stale file behind, then writes each given set.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        for stale in self.directory.glob("*.yml"):
            stale.unlink()
        for paper_set in paper_sets:
            self.save(paper_set)

    def load_all(self) -> list:
        """Load every `*.yml` file in the directory as PaperSet instances."""
        from snower.project import PaperSet

        return [
            PaperSet.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
            for p in sorted(self.directory.glob("*.yml"))
        ]
