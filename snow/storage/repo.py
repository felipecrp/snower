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

from snow.domain.identity import (
    BibliographicWork,
    WorkRef,
    mint_bib_key,
    normalize_doi,
    work_id as compute_work_id,
)
from snow.domain.models import (
    Criterion,
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
RESOLUTIONS_FILE = "resolutions.yml"
DECISIONS_PREFIX = "decisions_"

_SET_DIR_PATTERN = re.compile(r"^(\d{2})-(start|backward|forward)$")
_ORPHAN_DIR_PATTERN = re.compile(r"^orphan$")


def _as_identity_ref(work: BibliographicWork | WorkRef) -> WorkRef:
    return work.ref() if isinstance(work, BibliographicWork) else work


def _work_from_provider_result(work_id: str, ref: BibliographicWork | WorkRef) -> Work:
    return Work(
        id=work_id,
        bib_key="",
        title=ref.title or "",
        authors=list(ref.authors),
        year=ref.year,
        doi=ref.doi,
        venue=ref.venue if isinstance(ref, BibliographicWork) else None,
        url=ref.url if isinstance(ref, BibliographicWork) else None,
        pdf_url=ref.pdf_url if isinstance(ref, BibliographicWork) else None,
        abstract=ref.abstract if isinstance(ref, BibliographicWork) else None,
    )


def _fill_missing_work_fields(existing: Work, incoming: Work) -> Work:
    return existing.model_copy(update={
        "doi": existing.doi or incoming.doi,
        "venue": existing.venue or incoming.venue,
        "url": existing.url or incoming.url,
        "pdf_url": existing.pdf_url or incoming.pdf_url,
        "abstract": existing.abstract or incoming.abstract,
    })


def _identity_ref_for_work(work: Work, *, include_doi: bool = True) -> WorkRef:
    return WorkRef(
        title=work.title,
        year=work.year,
        authors=tuple(work.authors),
        doi=work.doi if include_doi else None,
    )


def _canonicalize_work_id(work: Work) -> Work:
    canonical_id = compute_work_id(_identity_ref_for_work(work))
    if work.id == canonical_id:
        return work
    return work.model_copy(update={"id": canonical_id})


def _legacy_id_without_doi(work: Work) -> str:
    return compute_work_id(_identity_ref_for_work(work, include_doi=False))


def _normalized_doi(work: Work) -> str | None:
    return normalize_doi(work.doi) if work.doi else None


@dataclass
class SetPaths:
    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / SET_FILE

    @property
    def articles(self) -> Path:
        return self.root / ARTICLES_FILE


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
        regular = sorted(p.name for p in sets_dir.iterdir() if p.is_dir() and _SET_DIR_PATTERN.match(p.name))
        orphan = [p.name for p in sets_dir.iterdir() if p.is_dir() and _ORPHAN_DIR_PATTERN.match(p.name)]
        return regular + orphan

    def load_set(self, set_id: str) -> Set:
        regular_match = _SET_DIR_PATTERN.match(set_id)
        orphan_match = _ORPHAN_DIR_PATTERN.match(set_id)
        if not regular_match and not orphan_match:
            raise ValueError(f"Invalid set id: {set_id!r}")
        paths = self.set_dir(set_id)
        if not paths.root.exists():
            raise FileNotFoundError(set_id)
        metadata = yml.load(paths.metadata) or {}
        if regular_match:
            iteration = int(metadata.get("iteration", regular_match.group(1)))
            kind = SetKind(metadata.get("kind", regular_match.group(2)))
        else:
            iteration = int(metadata.get("iteration", 0))
            kind = SetKind.ORPHAN
        works = bib.load(paths.articles)
        self._merge_snowball_timestamps(works)
        return Set(
            id=set_id,
            kind=kind,
            iteration=iteration,
            works=works,
        )

    def save_set(self, s: Set) -> None:
        paths = self.set_dir(s.id)
        paths.root.mkdir(parents=True, exist_ok=True)
        yml.dump(
            s.model_dump(
                mode="json",
                include={"id", "kind", "iteration"},
                exclude_none=True,
            ),
            paths.metadata,
        )
        self._renormalize_keys(s.works)
        bib.dump(s.works, paths.articles)

    def _next_set_index(self) -> int:
        ids = [sid for sid in self.list_set_ids() if _SET_DIR_PATTERN.match(sid)]
        if not ids:
            return 0
        return max(int(sid.split("-", 1)[0]) for sid in ids) + 1

    # --- snowball log ---------------------------------------------------

    def snowballing_path(self) -> Path:
        return self.root / SNOWBALLING_FILE

    def load_snowball_log(self) -> dict[str, dict[str, dict]]:
        """Returns {direction: {bib_key: {at: iso_str, found: int | None}}}.

        Handles the legacy format where values were plain ISO timestamp strings.
        """
        data = yml.load(self.snowballing_path()) or {}
        result: dict[str, dict[str, dict]] = {}
        for direction in ("backward", "forward"):
            entries: dict[str, dict] = {}
            for key, value in dict(data.get(direction) or {}).items():
                if isinstance(value, str):
                    entries[key] = {"at": value, "found": None}
                else:
                    entries[key] = {"at": value.get("at", ""), "found": value.get("found")}
            result[direction] = entries
        return result

    def save_snowball_log(self, log: dict[str, dict[str, dict]]) -> None:
        yml.dump({"backward": log.get("backward", {}), "forward": log.get("forward", {})}, self.snowballing_path())

    def _merge_snowball_timestamps(self, works: list[Work]) -> None:
        log = self.load_snowball_log()
        bwd = log.get("backward", {})
        fwd = log.get("forward", {})
        for work in works:
            if work.bib_key in bwd:
                entry = bwd[work.bib_key]
                work.last_backward_snowballed_at = datetime.fromisoformat(entry["at"])
                work.last_backward_found = entry.get("found")
            if work.bib_key in fwd:
                entry = fwd[work.bib_key]
                work.last_forward_snowballed_at = datetime.fromisoformat(entry["at"])
                work.last_forward_found = entry.get("found")

    def run_global_snowballing(self, kind: SetKind, provider, force: bool = False) -> list[Set]:  # type: ignore[type-arg]
        """Fetch references (backward) or citations (forward) for all accepted works.

        When force=False (default), skips works already snowballed in that direction.
        When force=True, re-processes all consensus-accepted works regardless.
        Returns all sets that were created or updated.
        """
        if kind == SetKind.START:
            raise ValueError("Snowballing kind must be backward or forward.")

        all_set_ids = [sid for sid in self.list_set_ids() if _SET_DIR_PATTERN.match(sid)]
        all_sets = [self.load_set(sid) for sid in all_set_ids]
        log = self.load_snowball_log()
        direction = kind.value  # "backward" or "forward"
        already_done: dict[str, str] = {} if force else log.setdefault(direction, {})

        logger.info("Starting %s snowballing (force=%s) — %d set(s) found", direction, force, len(all_sets))

        # All work_ids already present across all sets (for deduplication)
        all_known_ids: set[str] = {w.id for s in all_sets for w in s.works}

        # Group consensus-accepted, not-yet-snowballed works by their set's iteration
        to_process: dict[int, list[Work]] = defaultdict(list)
        for s in all_sets:
            decisions, _ = self.load_decisions(s.id)
            vote_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"accept": 0, "reject": 0})
            for d in decisions:
                key = "accept" if d.verdict == Verdict.ACCEPT else "reject"
                vote_counts[d.work_id][key] += 1
            accepted_ids = {wid for wid, v in vote_counts.items() if v["accept"] > v["reject"]}

            n_accepted = n_done = n_queued = 0
            for work in s.works:
                if work.id not in accepted_ids:
                    pass
                elif work.bib_key in already_done:
                    n_done += 1
                else:
                    n_queued += 1
                    to_process[s.iteration].append(work)
            n_accepted = len(accepted_ids)
            logger.info(
                "  %s: %d work(s) total — %d consensus-accepted, %d already snowballed, %d queued",
                s.id, len(s.works), n_accepted, n_done, n_queued,
            )

        if not to_process:
            logger.info("Nothing to do — no eligible papers for %s snowballing", direction)
            return []

        updated_sets: list[Set] = []
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        existing_relations = self.load_relations()
        known_edges: set[tuple[str, str]] = {(r.citing_bib_key, r.cited_bib_key) for r in existing_relations}
        # Collect raw edges as work_id pairs; converted to bib_keys after save_set.
        pending_edges: list[tuple[str, str]] = []  # (citing_work_id, cited_work_id)

        for iteration, works in sorted(to_process.items()):
            target_iteration = iteration + 1
            target_id = f"{target_iteration:02d}-{direction}"

            try:
                target_set = self.load_set(target_id)
                target_known = {w.id for w in target_set.works}
                logger.info("Updating existing set %s", target_id)
            except FileNotFoundError:
                target_set = Set(
                    id=target_id,
                    kind=kind,
                    iteration=target_iteration,
                    works=[],
                )
                target_known = set()
                logger.info("Creating new set %s", target_id)

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

                added = 0
                for ref in refs:
                    wid = compute_work_id(_as_identity_ref(ref))
                    if kind == SetKind.BACKWARD:
                        pending_edges.append((work.id, wid))
                    else:
                        pending_edges.append((wid, work.id))

                    if wid in all_known_ids or wid in target_known:
                        continue
                    all_known_ids.add(wid)
                    target_known.add(wid)
                    added += 1
                    new_works.append(_work_from_provider_result(wid, ref))

                if refs:
                    logger.info(
                        "  %s: %d fetched — %d new, %d duplicate(s)",
                        work.bib_key, len(refs), added, len(refs) - added,
                    )
                else:
                    logger.warning("  %s: 0 results from provider", work.bib_key)

                already_done[work.bib_key] = {"at": now_iso, "found": len(refs)}

            logger.info("  → %d new work(s) added to %s", len(new_works), target_id)
            target_set.works.extend(new_works)
            self.save_set(target_set)  # assigns bib_keys via _renormalize_keys
            updated_sets.append(self.load_set(target_id))

        # Convert work_id edges to bib_key edges using the now-complete keys registry.
        id_to_key: dict[str, str] = {wid: key for key, wid in self.load_keys().items()}
        new_relations: list[Relation] = []
        for citing_id, cited_id in pending_edges:
            citing_key = id_to_key.get(citing_id)
            cited_key = id_to_key.get(cited_id)
            if not citing_key or not cited_key:
                continue
            edge = (citing_key, cited_key)
            if edge in known_edges:
                continue
            known_edges.add(edge)
            new_relations.append(Relation(citing_bib_key=citing_key, cited_bib_key=cited_key))

        logger.info(
            "%s snowballing done — %d set(s) updated",
            direction.capitalize(), len(updated_sets),
        )
        self.save_snowball_log(log)
        if new_relations:
            self.save_relations(existing_relations + new_relations)
            logger.info("%d new relation(s) saved to relations.yml", len(new_relations))
        return updated_sets

    # --- decisions ------------------------------------------------------

    def _researcher_decisions_path(self, set_id: str, researcher_id: str) -> Path:
        return self.set_dir(set_id).root / f"{DECISIONS_PREFIX}{researcher_id}.yml"

    def _resolutions_path(self, set_id: str) -> Path:
        return self.set_dir(set_id).root / RESOLUTIONS_FILE

    def load_decisions(self, set_id: str) -> tuple[list[Decision], list[Resolution]]:
        set_dir = self.set_dir(set_id).root
        decisions: list[Decision] = []
        for f in sorted(set_dir.glob(f"{DECISIONS_PREFIX}*.yml")):
            data = yml.load(f) or {}
            decisions.extend(Decision.model_validate(d) for d in data.get("decisions", []))
        resolutions_data = yml.load(self._resolutions_path(set_id)) or {}
        resolutions = [Resolution.model_validate(r) for r in resolutions_data.get("resolutions", [])]
        return decisions, resolutions

    def save_researcher_decision(self, set_id: str, decision: Decision) -> None:
        path = self._researcher_decisions_path(set_id, decision.researcher_id)
        self.set_dir(set_id).root.mkdir(parents=True, exist_ok=True)
        data = yml.load(path) or {}
        existing = [Decision.model_validate(d) for d in data.get("decisions", [])]
        existing = [d for d in existing if d.work_id != decision.work_id]
        existing.append(decision)
        yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in existing]}, path)

    def delete_researcher_decision(self, set_id: str, work_id: str, researcher_id: str) -> None:
        path = self._researcher_decisions_path(set_id, researcher_id)
        data = yml.load(path) or {}
        existing = [Decision.model_validate(d) for d in data.get("decisions", [])]
        remaining = [d for d in existing if d.work_id != work_id]
        yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in remaining]}, path)

    def save_decisions(
        self,
        set_id: str,
        decisions: list[Decision],
        resolutions: list[Resolution] | None = None,
    ) -> None:
        """Batch write: replaces all per-researcher files for this set.

        Clears existing decision files first so stale files (e.g. after a rename)
        don't linger and get re-read by load_decisions.
        Used by tests, bulk operations, and the project rename/delete flows.
        """
        set_dir = self.set_dir(set_id).root
        set_dir.mkdir(parents=True, exist_ok=True)
        for old_file in set_dir.glob(f"{DECISIONS_PREFIX}*.yml"):
            old_file.unlink()
        by_researcher: dict[str, list[Decision]] = {}
        for d in decisions:
            by_researcher.setdefault(d.researcher_id, []).append(d)
        for researcher_id, researcher_decisions in by_researcher.items():
            path = self._researcher_decisions_path(set_id, researcher_id)
            yml.dump(
                {"decisions": [d.model_dump(mode="json", exclude_none=True) for d in researcher_decisions]},
                path,
            )
        if resolutions:
            yml.dump(
                {"resolutions": [r.model_dump(mode="json", exclude_none=True) for r in resolutions]},
                self._resolutions_path(set_id),
            )

    # --- key registry ---------------------------------------------------

    def keys_path(self) -> Path:
        return self.root / KEYS_FILE

    def load_keys(self) -> dict[str, str]:
        """Mapping of bib_key -> work_id for the whole project."""
        data = yml.load(self.keys_path()) or {}
        return dict(data.get("keys", {}))

    def save_keys(self, keys: dict[str, str]) -> None:
        yml.dump({"keys": dict(sorted(keys.items()))}, self.keys_path())

    def _remap_work_id(self, set_id: str, old_id: str, new_id: str, bib_key: str) -> None:
        if old_id == new_id:
            return

        keys = self.load_keys()
        if bib_key and keys.get(bib_key) == old_id:
            keys[bib_key] = new_id
            self.save_keys(keys)

        set_dir = self.set_dir(set_id).root
        for dec_file in sorted(set_dir.glob(f"{DECISIONS_PREFIX}*.yml")):
            data = yml.load(dec_file) or {}
            decisions = [Decision.model_validate(d) for d in data.get("decisions", [])]
            changed = False
            remapped: list[Decision] = []
            for decision in decisions:
                if decision.work_id == old_id:
                    remapped.append(decision.model_copy(update={"work_id": new_id}))
                    changed = True
                else:
                    remapped.append(decision)
            if changed:
                yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in remapped]}, dec_file)

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
        relations: list[Relation] = []
        seen: set[tuple[str, str]] = set()
        for entry in data.get("relations") or []:
            for bib_key, connections in entry.items():
                for cited in connections.get("cite") or []:
                    edge = (bib_key, cited)
                    if edge not in seen:
                        seen.add(edge)
                        relations.append(Relation(citing_bib_key=bib_key, cited_bib_key=cited))
        return relations

    def save_relations(self, relations: list[Relation]) -> None:
        grouped: dict[str, dict[str, list[str]]] = {}
        for r in relations:
            grouped.setdefault(r.citing_bib_key, {"cite": [], "cited_by": []})["cite"].append(r.cited_bib_key)
            grouped.setdefault(r.cited_bib_key, {"cite": [], "cited_by": []})["cited_by"].append(r.citing_bib_key)
        entries = [{key: val} for key, val in sorted(grouped.items())]
        yml.dump({"relations": entries}, self.relations_path())

    def _move_work(self, work_id: str, from_set_id: str, to_set_id: str) -> None:
        """Move a work and its per-researcher decisions from one set to another."""
        from_set = self.load_set(from_set_id)
        to_set = self.load_set(to_set_id)

        work = next((w for w in from_set.works if w.id == work_id), None)
        if not work:
            return

        from_set.works = [w for w in from_set.works if w.id != work_id]
        to_set.works.append(work)
        self.save_set(from_set)
        self.save_set(to_set)

        from_dir = self.set_dir(from_set_id).root
        for dec_file in sorted(from_dir.glob(f"{DECISIONS_PREFIX}*.yml")):
            researcher_id = dec_file.stem[len(DECISIONS_PREFIX):]
            data = yml.load(dec_file) or {}
            all_dec = [Decision.model_validate(d) for d in data.get("decisions", [])]
            to_move = [d for d in all_dec if d.work_id == work_id]
            remaining = [d for d in all_dec if d.work_id != work_id]
            if remaining:
                yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in remaining]}, dec_file)
            else:
                dec_file.unlink()
            for d in to_move:
                self.save_researcher_decision(to_set_id, d)
        logger.info("Moved work %s from %s to %s", work_id, from_set_id, to_set_id)

    def run_paper_snowballing(self, kind: SetKind, bib_key: str, provider) -> list["Set"]:  # type: ignore[type-arg]
        """Fetch references/citations for a single paper identified by bib_key.

        After collecting new papers, applies graph rebalancing: if a found paper
        already lives in a set at a later iteration, it is moved to the earlier
        target set so the snowballing graph stays consistent.
        """
        if kind == SetKind.START:
            raise ValueError("Snowballing kind must be backward or forward.")

        all_set_ids = [sid for sid in self.list_set_ids() if _SET_DIR_PATTERN.match(sid)]
        all_sets = [self.load_set(sid) for sid in all_set_ids]

        source_set: Set | None = None
        source_work: Work | None = None
        for s in all_sets:
            for w in s.works:
                if w.bib_key == bib_key:
                    source_set = s
                    source_work = w
                    break
            if source_work:
                break

        if not source_work or not source_set:
            raise ValueError(f"Work {bib_key!r} not found in any set.")

        decisions, _ = self.load_decisions(source_set.id)
        votes = {"accept": 0, "reject": 0}
        for d in decisions:
            if d.work_id != source_work.id:
                continue
            votes["accept" if d.verdict == Verdict.ACCEPT else "reject"] += 1
        if votes["accept"] <= votes["reject"]:
            raise ValueError(
                f"Snowballing only allowed for consensus-accepted papers; {bib_key!r} is not accepted.",
            )

        direction = kind.value
        target_iteration = source_set.iteration + 1
        target_id = f"{target_iteration:02d}-{direction}"

        log = self.load_snowball_log()
        already_done = log.setdefault(direction, {})

        all_known: dict[str, tuple[Set, Work]] = {}
        for s in all_sets:
            for w in s.works:
                all_known[w.id] = (s, w)

        try:
            target_set = self.load_set(target_id)
        except FileNotFoundError:
            target_set = Set(id=target_id, kind=kind, iteration=target_iteration, works=[])

        target_known: set[str] = {w.id for w in target_set.works}

        try:
            if kind == SetKind.BACKWARD:
                refs = provider.fetch_references(source_work)
            else:
                refs = provider.fetch_citations(source_work)
        except Exception as exc:
            logger.error("Provider error for %r: %s", source_work.title, exc)
            refs = []

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        existing_relations = self.load_relations()
        known_edges: set[tuple[str, str]] = {(r.citing_bib_key, r.cited_bib_key) for r in existing_relations}
        pending_edges: list[tuple[str, str]] = []
        moves: list[tuple[str, str]] = []  # (work_id, from_set_id) to move into target

        for ref in refs:
            wid = compute_work_id(_as_identity_ref(ref))
            if kind == SetKind.BACKWARD:
                pending_edges.append((source_work.id, wid))
            else:
                pending_edges.append((wid, source_work.id))

            if wid in target_known:
                continue

            if wid in all_known:
                existing_set, _ = all_known[wid]
                if existing_set.iteration > target_iteration:
                    moves.append((wid, existing_set.id))
                    target_known.add(wid)
            else:
                target_set.works.append(_work_from_provider_result(wid, ref))
                target_known.add(wid)

        already_done[bib_key] = {"at": now_iso, "found": len(refs)}
        self.save_set(target_set)
        self.save_snowball_log(log)

        moved_from_ids: list[str] = []
        for work_id, from_set_id in moves:
            self._move_work(work_id, from_set_id, target_id)
            if from_set_id not in moved_from_ids:
                moved_from_ids.append(from_set_id)

        id_to_key: dict[str, str] = {wid: key for key, wid in self.load_keys().items()}
        new_relations: list[Relation] = []
        for citing_id, cited_id in pending_edges:
            citing_key = id_to_key.get(citing_id)
            cited_key = id_to_key.get(cited_id)
            if not citing_key or not cited_key:
                continue
            edge = (citing_key, cited_key)
            if edge in known_edges:
                continue
            known_edges.add(edge)
            new_relations.append(Relation(citing_bib_key=citing_key, cited_bib_key=cited_key))
        if new_relations:
            self.save_relations(existing_relations + new_relations)

        updated = [self.load_set(target_id)]
        for from_id in moved_from_ids:
            updated.append(self.load_set(from_id))
        return updated

    def _move_decisions_between(self, work_id: str, from_set_id: str, to_set_id: str) -> None:
        from_dir = self.set_dir(from_set_id).root
        if not from_dir.exists():
            return
        for dec_file in sorted(from_dir.glob(f"{DECISIONS_PREFIX}*.yml")):
            data = yml.load(dec_file) or {}
            all_dec = [Decision.model_validate(d) for d in data.get("decisions", [])]
            to_move = [d for d in all_dec if d.work_id == work_id]
            remaining = [d for d in all_dec if d.work_id != work_id]
            if remaining:
                yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in remaining]}, dec_file)
            else:
                dec_file.unlink()
            for d in to_move:
                self.save_researcher_decision(to_set_id, d)

    def _sync_orphan_direction(
        self,
        source_set_ids: list[str],
        direction: str,
        is_connected: set[str],
    ) -> None:
        """Move disconnected works from source sets to the orphan set; recover connected works back."""
        orphan_set_id = "orphan"
        try:
            orphan_set = self.load_set(orphan_set_id)
        except FileNotFoundError:
            orphan_set = Set(id=orphan_set_id, kind=SetKind.ORPHAN, iteration=0, works=[])

        # Step 1: Return recovered works from orphan set to their origins.
        orphan_remaining: list[Work] = []
        for w in orphan_set.works:
            if w.extra.get("_snow_direction") != direction or w.bib_key not in is_connected:
                orphan_remaining.append(w)
                continue
            origin_id = w.extra.get("_snow_origin")
            returned = False
            if origin_id:
                try:
                    origin_set = self.load_set(origin_id)
                    if w.id not in {ow.id for ow in origin_set.works}:
                        restored = w.model_copy(deep=True)
                        restored.extra.pop("_snow_origin", None)
                        restored.extra.pop("_snow_direction", None)
                        origin_set.works.append(restored)
                        self.save_set(origin_set)
                        self._move_decisions_between(w.id, orphan_set_id, origin_id)
                        returned = True
                        logger.info("Returned work %s from orphan to %s", w.bib_key, origin_id)
                except (FileNotFoundError, ValueError):
                    pass
            if not returned:
                orphan_remaining.append(w)
        orphan_set.works = orphan_remaining

        # Step 2: Move disconnected works from source sets to orphan.
        orphan_ids = {w.id for w in orphan_set.works}
        new_orphans: list[Work] = []

        for source_id in source_set_ids:
            source = self.load_set(source_id)
            to_keep: list[Work] = []
            to_orphan: list[Work] = []
            for w in source.works:
                if w.bib_key in is_connected:
                    to_keep.append(w)
                else:
                    marked = w.model_copy(deep=True)
                    marked.extra["_snow_origin"] = source_id
                    marked.extra["_snow_direction"] = direction
                    to_orphan.append(marked)

            if to_orphan:
                source.works = to_keep
                self.save_set(source)
                for w in to_orphan:
                    if w.id not in orphan_ids:
                        new_orphans.append(w)
                        orphan_ids.add(w.id)
                        self._move_decisions_between(w.id, source_id, orphan_set_id)
                        logger.info("Orphaned work %s from %s", w.bib_key, source_id)

        orphan_set.works = orphan_remaining + new_orphans
        self.save_set(orphan_set)

    def recalculate_orphans(self) -> None:
        """Rebalance backward/forward sets and the orphan set based on current consensus.

        A paper found by backward snowballing is orphaned when no accepted paper cites it.
        A paper found by forward snowballing is orphaned when it cites no accepted paper.
        Works carry _snow_origin (original set) and _snow_direction in their extra fields.
        They are returned when they regain a connection to an accepted paper.
        """
        regular_ids = [sid for sid in self.list_set_ids() if _SET_DIR_PATTERN.match(sid)]
        regular_sets = {sid: self.load_set(sid) for sid in regular_ids}

        # Compute consensus-accepted bib_keys across all regular sets.
        accepted_bib_keys: set[str] = set()
        for sid, s in regular_sets.items():
            decisions, _ = self.load_decisions(sid)
            vote_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"accept": 0, "reject": 0})
            for d in decisions:
                vote_counts[d.work_id]["accept" if d.verdict == Verdict.ACCEPT else "reject"] += 1
            for w in s.works:
                if vote_counts[w.id]["accept"] > vote_counts[w.id]["reject"]:
                    accepted_bib_keys.add(w.bib_key)

        relations = self.load_relations()
        cited_by_accepted = {r.cited_bib_key for r in relations if r.citing_bib_key in accepted_bib_keys}
        cites_accepted = {r.citing_bib_key for r in relations if r.cited_bib_key in accepted_bib_keys}

        backward_ids = [sid for sid in regular_ids if regular_sets[sid].kind == SetKind.BACKWARD]
        forward_ids = [sid for sid in regular_ids if regular_sets[sid].kind == SetKind.FORWARD]

        self._sync_orphan_direction(backward_ids, "backward", cited_by_accepted)
        self._sync_orphan_direction(forward_ids, "forward", cites_accepted)

    def import_bib_to_set(
        self,
        set_id: str,
        new_works: list[Work],
        criteria: list[Criterion] | None = None,
        researcher_id: str | None = None,
    ) -> Set:
        """Add works from a BibTeX import to an existing set, deduplicating.

        If criteria and researcher_id are provided, creates decisions for works
        whose `groups` field matches a criterion ID.
        """
        try:
            existing = self.load_set(set_id)
        except FileNotFoundError:
            raise ValueError(f"Set not found: {set_id}")

        new_works = [_canonicalize_work_id(w) for w in new_works]
        existing_by_id = {w.id: i for i, w in enumerate(existing.works)}
        existing_by_legacy_id = {_legacy_id_without_doi(w): i for i, w in enumerate(existing.works)}
        existing_by_doi = {
            doi: i
            for i, w in enumerate(existing.works)
            if (doi := _normalized_doi(w))
        }
        added: list[Work] = []
        for w in new_works:
            existing_index = existing_by_id.get(w.id)
            if existing_index is None:
                doi = _normalized_doi(w)
                if doi:
                    existing_index = existing_by_doi.get(doi)
            if existing_index is None:
                existing_index = existing_by_legacy_id.get(_legacy_id_without_doi(w))

            if existing_index is not None:
                current = existing.works[existing_index]
                merged = _canonicalize_work_id(_fill_missing_work_fields(current, w))
                if current.id != merged.id:
                    self._remap_work_id(set_id, current.id, merged.id, current.bib_key)
                existing.works[existing_index] = merged
                existing_by_id[merged.id] = existing_index
                existing_by_legacy_id[_legacy_id_without_doi(merged)] = existing_index
                if doi := _normalized_doi(merged):
                    existing_by_doi[doi] = existing_index
            else:
                existing.works.append(w)
                added.append(w)
                new_index = len(existing.works) - 1
                existing_by_id[w.id] = new_index
                existing_by_legacy_id[_legacy_id_without_doi(w)] = new_index
                if doi := _normalized_doi(w):
                    existing_by_doi[doi] = new_index
        self.save_set(existing)

        if criteria and researcher_id:
            criterion_by_id = {c.id: c for c in criteria}
            now = datetime.now(timezone.utc)
            for w in new_works:
                groups_raw = w.extra.get("groups", "")
                groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
                for group in groups:
                    if group in criterion_by_id:
                        c = criterion_by_id[group]
                        verdict = Verdict.ACCEPT if c.kind == "include" else Verdict.REJECT
                        decision = Decision(
                            work_id=w.id,
                            researcher_id=researcher_id,
                            verdict=verdict,
                            criterion_id=c.id,
                            note=None,
                            decided_at=now,
                        )
                        self.save_researcher_decision(set_id, decision)
                        break

        return self.load_set(set_id)

    # --- bootstrap ------------------------------------------------------

    def init(self, project: Project) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.save_project(project)
        self.ensure_scaffolding()

    def ensure_scaffolding(self) -> None:
        """Idempotently create the directory layout and the empty start set."""
        self.sets_dir().mkdir(parents=True, exist_ok=True)
        if not self.relations_path().exists():
            self.save_relations([])
        if not self.set_dir("00-start").root.exists():
            self.save_set(Set(id="00-start", kind=SetKind.START, iteration=0, works=[]))

    def import_start_set(self, works: list[Work]) -> Set:
        works = [_canonicalize_work_id(w) for w in works]
        start = Set(id="00-start", kind=SetKind.START, iteration=0, works=works)
        self.save_set(start)
        return start
