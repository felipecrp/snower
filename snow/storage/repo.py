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

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from snow.domain.identity import WorkRef, mint_bib_key, work_id as compute_work_id
from snow.domain.models import (
    Decision,
    Project,
    Relation,
    Resolution,
    Set,
    SetKind,
    Verdict,
    Work,
)
from snow.storage import bib, yml

logger = logging.getLogger(__name__)

PROJECT_FILE = "project.yml"
RELATIONS_FILE = "relations.yml"
KEYS_FILE = "keys.yml"
SNOWBALLING_FILE = "snowballing.yml"
SETS_DIR = "sets"
SET_FILE = "set.yml"
ARTICLES_FILE = "articles.bib"
DECISIONS_FILE = "decisions.yml"

_SET_DIR_PATTERN = re.compile(r"^(\d{2})-(start|backward|forward)$")


@dataclass
class SetPaths:
    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / SET_FILE

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
        paths = self.set_dir(set_id)
        if not paths.root.exists():
            raise FileNotFoundError(set_id)
        metadata = yml.load(paths.metadata) or {}
        iteration = int(metadata.get("iteration", match.group(1)))
        kind = SetKind(metadata.get("kind", match.group(2)))
        parent_set_id = metadata.get("parent_set_id")
        works = bib.load(paths.articles)
        self._merge_snowball_timestamps(works)
        return Set(
            id=set_id,
            kind=kind,
            iteration=iteration,
            parent_set_id=parent_set_id,
            works=works,
        )

    def save_set(self, s: Set) -> None:
        paths = self.set_dir(s.id)
        paths.root.mkdir(parents=True, exist_ok=True)
        yml.dump(
            s.model_dump(
                mode="json",
                include={"id", "kind", "iteration", "parent_set_id"},
                exclude_none=True,
            ),
            paths.metadata,
        )
        self._renormalize_keys(s.works)
        bib.dump(s.works, paths.articles)

    def start_snowballing(self, parent_set_id: str, kind: SetKind) -> Set:
        parent = self.load_set(parent_set_id)
        new_set = Set(
            id=f"{self._next_set_index():02d}-{kind.value}",
            kind=kind,
            iteration=parent.iteration + 1,
            parent_set_id=parent.id,
            works=[],
        )
        self.save_set(new_set)
        return new_set

    def _next_set_index(self) -> int:
        ids = self.list_set_ids()
        if not ids:
            return 0
        return max(int(sid.split("-", 1)[0]) for sid in ids) + 1

    # --- snowball log ---------------------------------------------------

    def snowballing_path(self) -> Path:
        return self.root / SNOWBALLING_FILE

    def load_snowball_log(self) -> dict[str, dict[str, str]]:
        """Returns {direction: {work_id: iso_timestamp}}."""
        data = yml.load(self.snowballing_path()) or {}
        return {
            "backward": dict(data.get("backward", {})),
            "forward": dict(data.get("forward", {})),
        }

    def save_snowball_log(self, log: dict[str, dict[str, str]]) -> None:
        yml.dump({"backward": log.get("backward", {}), "forward": log.get("forward", {})}, self.snowballing_path())

    def _merge_snowball_timestamps(self, works: list[Work]) -> None:
        log = self.load_snowball_log()
        bwd = log.get("backward", {})
        fwd = log.get("forward", {})
        for work in works:
            if work.id in bwd:
                work.last_backward_snowballed_at = datetime.fromisoformat(bwd[work.id])
            if work.id in fwd:
                work.last_forward_snowballed_at = datetime.fromisoformat(fwd[work.id])

    def run_global_snowballing(self, kind: SetKind, provider) -> list[Set]:  # type: ignore[type-arg]
        """Fetch references (backward) or citations (forward) for all accepted works
        not yet snowballed in that direction. Groups by source set iteration N and
        adds results to the set at iteration N+1, creating it when needed.
        Returns all sets that were created or updated.
        """
        if kind == SetKind.START:
            raise ValueError("Snowballing kind must be backward or forward.")

        all_set_ids = self.list_set_ids()
        all_sets = [self.load_set(sid) for sid in all_set_ids]
        log = self.load_snowball_log()
        direction = kind.value  # "backward" or "forward"
        already_done: dict[str, str] = log.setdefault(direction, {})

        # All work_ids already present across all sets (for deduplication)
        all_known_ids: set[str] = {w.id for s in all_sets for w in s.works}

        # Group accepted, not-yet-snowballed works by their set's iteration
        to_process: dict[int, list[Work]] = defaultdict(list)
        for s in all_sets:
            decisions, _ = self.load_decisions(s.id)
            accepted_ids = {d.work_id for d in decisions if d.verdict == Verdict.ACCEPT}
            for work in s.works:
                if work.id in accepted_ids and work.id not in already_done:
                    to_process[s.iteration].append(work)

        if not to_process:
            return []

        updated_sets: list[Set] = []
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        for iteration, works in sorted(to_process.items()):
            target_iteration = iteration + 1
            target_id = f"{target_iteration:02d}-{direction}"

            try:
                target_set = self.load_set(target_id)
                target_known = {w.id for w in target_set.works}
            except FileNotFoundError:
                target_set = Set(
                    id=target_id,
                    kind=kind,
                    iteration=target_iteration,
                    works=[],
                )
                target_known = set()

            new_works: list[Work] = []
            for work in works:
                try:
                    if kind == SetKind.BACKWARD:
                        refs = provider.fetch_references(work)
                    else:
                        refs = provider.fetch_citations(work)
                except Exception as exc:
                    logger.error("Provider error for '%s': %s", work.title, exc)
                    refs = []

                for ref in refs:
                    wid = compute_work_id(ref)
                    if wid in all_known_ids or wid in target_known:
                        continue
                    all_known_ids.add(wid)
                    target_known.add(wid)
                    new_works.append(
                        Work(
                            id=wid,
                            bib_key="",
                            title=ref.title or "",
                            authors=list(ref.authors),
                            year=ref.year,
                            doi=ref.doi,
                        )
                    )

                already_done[work.id] = now_iso

            target_set.works.extend(new_works)
            self.save_set(target_set)
            updated_sets.append(self.load_set(target_id))

        self.save_snowball_log(log)
        return updated_sets

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
