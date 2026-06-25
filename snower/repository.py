from pathlib import Path

import yaml

from snower.paper import Paper
from snower.review import Assessment


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
            yaml.safe_dump(paper.model_dump(mode="json", exclude={"decision"}), sort_keys=False, allow_unicode=True),
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
        """Return the YAML file name for a set.

        Directional sets use ``{name}-{round}.yml``; special sets without a
        meaningful round (``start_set``, ``orphans``) use ``{name}.yml``.
        """
        escaped = paper_set.name.replace(" ", "_")
        if paper_set.round is None:
            return f"{escaped}.yml"
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


class ReviewRepository:
    """File-backed store of per-researcher assessments, one YAML file per
    researcher named ``{email}.yml`` under a base directory.

    Files are rewritten in full on every save; the ``review/`` directory is the
    source of truth for assessments between server restarts.
    """

    def __init__(self, directory: str | Path) -> None:
        """Initialise with the path to the ``review/`` storage directory."""
        self.directory = Path(directory)

    def save_all(self, assessments: dict[str, dict[str, Assessment]]) -> None:
        """Replace the directory's contents with all researcher assessments.

        Clears every existing ``*.yml`` first (so a deleted researcher's file
        disappears), then writes one ``{email}.yml`` per researcher. Each file
        records only ``criterion_id`` and ``phase_id`` per paper, sorted by
        bib_id for merge-friendly diffs. Researchers with no assessments are skipped.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        for stale in self.directory.glob("*.yml"):
            stale.unlink()
        for email, papers in assessments.items():
            if not papers:
                continue
            path = self.directory / f"{email}.yml"
            data = {
                bib_id: {
                    "criterion_id": a.criterion.id,
                    "phase_id": a.phase.id,
                    **({"comment": a.comment} if a.comment else {}),
                }
                for bib_id, a in sorted(papers.items())
            }
            path.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

    def load_all(
        self,
        criteria: list | None = None,
        phases: list | None = None,
    ) -> dict[str, dict[str, Assessment]]:
        """Read each ``*.yml`` file; stem → email, contents → {bib_id: Assessment}.

        Resolves ``criterion_id`` and ``phase_id`` against the provided lists.
        Also handles the legacy embedded format for backward compatibility.
        """
        from snower.review import Criterion, Phase

        criteria_map = {c.id: c for c in (criteria or [])}
        phases_map = {p.id: p for p in (phases or [])}
        result: dict[str, dict[str, Assessment]] = {}
        for path in sorted(self.directory.glob("*.yml")):
            email = path.stem
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            assessments: dict[str, Assessment] = {}
            for bib_id, v in raw.items():
                if "criterion_id" in v:
                    criterion = criteria_map.get(v["criterion_id"])
                    phase = phases_map.get(v["phase_id"])
                    if criterion and phase:
                        assessments[bib_id] = Assessment(
                            criterion=criterion,
                            phase=phase,
                            comment=v.get("comment"),
                        )
                else:
                    assessments[bib_id] = Assessment.model_validate(v)
            result[email] = assessments
        return result
