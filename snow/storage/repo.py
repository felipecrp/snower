"""Project directory layout and I/O.

A project on disk looks like:

    <project>/
        project.yml
        relations.yml
        sets/
            00-start/
                articles.bib
                decisions.yml
            01-backward/
                ...

This module owns reading and writing that tree. Higher layers (API, CLI)
operate on the domain models and call into here for persistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from snow.domain.identity import WorkRef, mint_bib_key
from snow.domain.models import (
    Decision,
    Project,
    Relation,
    Resolution,
    Set,
    SetKind,
    Work,
)
from snow.storage import bib, yml

PROJECT_FILE = "project.yml"
RELATIONS_FILE = "relations.yml"
KEYS_FILE = "keys.yml"
SETS_DIR = "sets"
ARTICLES_FILE = "articles.bib"
DECISIONS_FILE = "decisions.yml"

_SET_DIR_PATTERN = re.compile(r"^(\d{2})-(start|backward|forward)$")


@dataclass
class SetPaths:
    root: Path

    @property
    def articles(self) -> Path:
        return self.root / ARTICLES_FILE

    @property
    def decisions(self) -> Path:
        return self.root / DECISIONS_FILE


class ProjectRepo:
    """Filesystem-backed repository for a single project."""

    def __init__(self, root: Path) -> None:
        self.root = root

    # --- project --------------------------------------------------------

    def project_path(self) -> Path:
        return self.root / PROJECT_FILE

    def load_project(self) -> Project:
        data = yml.load(self.project_path()) or {}
        return Project.model_validate(data)

    def save_project(self, project: Project) -> None:
        yml.dump(project.model_dump(mode="json", exclude_none=True), self.project_path())

    # --- sets -----------------------------------------------------------

    def sets_dir(self) -> Path:
        return self.root / SETS_DIR

    def set_dir(self, set_id: str) -> SetPaths:
        return SetPaths(self.sets_dir() / set_id)

    def list_set_ids(self) -> list[str]:
        sets_dir = self.sets_dir()
        if not sets_dir.exists():
            return []
        ids = [p.name for p in sets_dir.iterdir() if p.is_dir() and _SET_DIR_PATTERN.match(p.name)]
        return sorted(ids)

    def load_set(self, set_id: str) -> Set:
        match = _SET_DIR_PATTERN.match(set_id)
        if not match:
            raise ValueError(f"Invalid set id: {set_id!r}")
        iteration = int(match.group(1))
        kind = SetKind(match.group(2))
        works = bib.load(self.set_dir(set_id).articles)
        return Set(id=set_id, kind=kind, iteration=iteration, works=works)

    def save_set(self, s: Set) -> None:
        paths = self.set_dir(s.id)
        paths.root.mkdir(parents=True, exist_ok=True)
        self._renormalize_keys(s.works)
        bib.dump(s.works, paths.articles)

    # --- decisions ------------------------------------------------------

    def load_decisions(self, set_id: str) -> tuple[list[Decision], list[Resolution]]:
        data = yml.load(self.set_dir(set_id).decisions) or {}
        decisions = [Decision.model_validate(d) for d in data.get("decisions", [])]
        resolutions = [Resolution.model_validate(r) for r in data.get("resolutions", [])]
        return decisions, resolutions

    def save_decisions(
        self,
        set_id: str,
        decisions: list[Decision],
        resolutions: list[Resolution] | None = None,
    ) -> None:
        paths = self.set_dir(set_id)
        paths.root.mkdir(parents=True, exist_ok=True)
        data = {
            "decisions": [d.model_dump(mode="json", exclude_none=True) for d in decisions],
            "resolutions": [
                r.model_dump(mode="json", exclude_none=True) for r in (resolutions or [])
            ],
        }
        yml.dump(data, paths.decisions)

    # --- key registry ---------------------------------------------------

    def keys_path(self) -> Path:
        return self.root / KEYS_FILE

    def load_keys(self) -> dict[str, str]:
        """Mapping of bib_key -> work_id for the whole project."""
        data = yml.load(self.keys_path()) or {}
        return dict(data.get("keys", {}))

    def save_keys(self, keys: dict[str, str]) -> None:
        yml.dump({"keys": dict(sorted(keys.items()))}, self.keys_path())

    def _renormalize_keys(self, works: list[Work]) -> None:
        """Assign bib_keys following <surname><year><letter>, persisting in keys.yml.

        - Reuses an existing key when the work_id is already registered.
        - Mints a fresh letter suffix on first sight.
        """
        keys = self.load_keys()
        inverse: dict[str, str] = {v: k for k, v in keys.items()}
        taken: set[str] = set(keys.keys())

        for work in works:
            if work.id in inverse:
                work.bib_key = inverse[work.id]
                continue
            ref = WorkRef(
                title=work.title,
                year=work.year,
                authors=tuple(work.authors),
                doi=work.doi,
            )
            new_key = mint_bib_key(ref, taken)
            work.bib_key = new_key
            keys[new_key] = work.id
            inverse[work.id] = new_key
            taken.add(new_key)

        self.save_keys(keys)

    # --- relations ------------------------------------------------------

    def relations_path(self) -> Path:
        return self.root / RELATIONS_FILE

    def load_relations(self) -> list[Relation]:
        data = yml.load(self.relations_path()) or {}
        return [Relation.model_validate(r) for r in data.get("relations", [])]

    def save_relations(self, relations: list[Relation]) -> None:
        data = {"relations": [r.model_dump(mode="json") for r in relations]}
        yml.dump(data, self.relations_path())

    # --- bootstrap ------------------------------------------------------

    def init(self, project: Project) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.sets_dir().mkdir(exist_ok=True)
        self.save_project(project)
        if not self.relations_path().exists():
            self.save_relations([])

    def import_start_set(self, works: list[Work]) -> Set:
        start = Set(id="00-start", kind=SetKind.START, iteration=0, works=works)
        self.save_set(start)
        return start
