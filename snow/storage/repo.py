"""Project directory layout and I/O.

A project on disk looks like:

    <project>/
        project.yml
        keys.yml
        snowballing.yml
        relations/
            wohlin2014snowballing.yml  # one entry per paper in the citation graph
            ...
        works/
            wohlin2014snowballing.bib    # one entry per file, shared across sets
            ...
        sets/
            00-start/
                set.yml                  # includes `works: [bib_key, ...]`
                decisions_*.yml
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
    WorkRef,
    full_fingerprint,
    mint_bib_key,
    normalize_doi,
    short_fingerprint,
)
from snow.domain.models import (
    Bidding,
    BibliographicWork,
    Criterion,
    Decision,
    Phase,
    Project,
    Relation,
    Researcher,
    Resolution,
    Set,
    SetKind,
    Verdict,
    Work,
)
from snow.storage import bib, yml

logger = logging.getLogger(__name__)

PROJECT_FILE = "project.yml"
RELATIONS_DIR = "relations"
KEYS_FILE = "keys.yml"
SNOWBALLING_FILE = "snowballing.yml"
SETS_DIR = "sets"
SET_FILE = "set.yml"
WORKS_DIR = "works"
DOWNLOADS_DIR = "downloads"
RESEARCHERS_DIR = "researchers"
RESOLUTIONS_FILE = "resolutions.yml"
DECISIONS_PREFIX = "decisions_"
BIDDING_PREFIX = "bidding_"

_SET_DIR_PATTERN = re.compile(r"^(\d{2})-(start|backward|forward)$")
_ORPHAN_DIR_PATTERN = re.compile(r"^orphan$")


def _as_work_ref(ref: BibliographicWork | WorkRef) -> WorkRef:
    return ref.ref() if isinstance(ref, BibliographicWork) else ref


def _work_ref(work: Work) -> WorkRef:
    return WorkRef(title=work.title, year=work.year, authors=tuple(work.authors))


def _work_from_provider_result(ref: BibliographicWork | WorkRef) -> Work:
    return Work(
        bib_key="",  # assigned by _renormalize_keys
        title=ref.title or "",
        authors=list(ref.authors),
        year=ref.year,
        doi=ref.doi if isinstance(ref, BibliographicWork) else None,
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


def _normalized_doi(work: Work) -> str | None:
    return normalize_doi(work.doi) if work.doi else None


@dataclass
class KeyEntry:
    short: str
    bib_key: str


@dataclass
class SetPaths:
    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / SET_FILE


class ProjectRepo:
    """Filesystem-backed repository for a single project."""

    def __init__(self, root: Path) -> None:
        self.root = root

    # --- project --------------------------------------------------------

    def project_path(self) -> Path:
        return self.root / PROJECT_FILE

    def load_project(self) -> Project:
        data = yml.load(self.project_path()) or {}
        project = Project.model_validate(data)
        project.researchers = self.list_researchers()
        return project

    def save_project(self, project: Project) -> None:
        yml.dump(project.model_dump(mode="json", exclude_none=True, exclude={"researchers"}), self.project_path())

    # --- researchers (per-file) -----------------------------------------

    def researchers_dir(self) -> Path:
        return self.root / RESEARCHERS_DIR

    def researcher_path(self, email: str) -> Path:
        return self.researchers_dir() / f"{email}.yml"

    def list_researchers(self) -> list[Researcher]:
        rdir = self.researchers_dir()
        if not rdir.exists():
            return []
        researchers: list[Researcher] = []
        for path in sorted(rdir.glob("*.yml")):
            data = yml.load(path) or {}
            email = path.stem
            researchers.append(Researcher(
                email=email,
                name=data.get("name", email),
                assignment_percentage=int(data.get("assignment_percentage", 100)),
            ))
        return researchers

    def save_researcher(self, r: Researcher) -> None:
        self.researchers_dir().mkdir(parents=True, exist_ok=True)
        data: dict = {"name": r.name}
        if r.assignment_percentage != 100:
            data["assignment_percentage"] = r.assignment_percentage
        yml.dump(data, self.researcher_path(r.email))

    def delete_researcher(self, email: str) -> None:
        path = self.researcher_path(email)
        if path.exists():
            path.unlink()

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

    def works_dir(self) -> Path:
        return self.root / WORKS_DIR

    def work_path(self, bib_key: str) -> Path:
        return self.works_dir() / f"{bib_key}.bib"

    def downloads_dir(self) -> Path:
        return self.root / DOWNLOADS_DIR

    def relations_dir(self) -> Path:
        return self.root / RELATIONS_DIR

    def relation_path(self, bib_key: str) -> Path:
        return self.relations_dir() / f"{bib_key}.yml"

    def pdf_path(self, bib_key: str) -> Path:
        return self.downloads_dir() / f"{bib_key}.pdf"

    def load_work(self, bib_key: str) -> Work | None:
        path = self.work_path(bib_key)
        if not path.exists():
            return None
        entries = bib.load(path)
        return entries[0] if entries else None

    def save_work(self, work: Work) -> None:
        if not work.bib_key:
            raise ValueError("Cannot save work without bib_key")
        self.works_dir().mkdir(parents=True, exist_ok=True)
        bib.dump([work], self.work_path(work.bib_key))

    def merge_with_library(self, incoming: list[Work]) -> list[Work]:
        """Fill missing fields from `works/<bib_key>.bib` when the paper is already known.

        Looked up via full fingerprint (exact) then short fingerprint (fuzzy) in keys.yml.
        The on-disk version wins for any field it already has; incoming contributes only gaps.
        """
        keys = self.load_keys()
        full_to_bib_key = {fh: e.bib_key for fh, e in keys.items()}
        short_to_bib_key = {e.short: e.bib_key for e in keys.values()}
        merged: list[Work] = []
        for w in incoming:
            ref = _work_ref(w)
            bk = full_to_bib_key.get(full_fingerprint(ref)) or short_to_bib_key.get(short_fingerprint(ref))
            cached = self.load_work(bk) if bk else None
            if cached is None:
                merged.append(w)
            else:
                merged.append(_fill_missing_work_fields(cached, w))
        return merged

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
        bib_keys = list(metadata.get("works") or [])
        works: list[Work] = []
        for key in bib_keys:
            w = self.load_work(key)
            if w is None:
                logger.warning("Set %s lists bib_key %s but %s is missing", set_id, key, self.work_path(key))
                continue
            w.has_local_pdf = self.pdf_path(key).exists()
            works.append(w)
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
        self._renormalize_keys(s.works)  # assigns bib_keys and updates keys.yml
        for w in s.works:
            self.save_work(w)
        metadata = {
            "id": s.id,
            "kind": s.kind.value,
            "iteration": s.iteration,
            "works": [w.bib_key for w in s.works],
        }
        yml.dump(metadata, paths.metadata)

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

        # Use full fingerprints for deduplication; keys.yml is the registry.
        keys = self.load_keys()
        all_known_hashes: set[str] = set(keys.keys())
        full_to_bib_key: dict[str, str] = {fh: e.bib_key for fh, e in keys.items()}
        short_to_bib_key: dict[str, str] = {e.short: e.bib_key for e in keys.values()}

        # Group consensus-accepted, not-yet-snowballed works by their set's iteration
        to_process: dict[int, list[Work]] = defaultdict(list)
        for s in all_sets:
            decisions, _ = self.load_decisions(s.id)
            vote_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"accept": 0, "reject": 0})
            for d in decisions:
                key = "accept" if d.verdict == Verdict.ACCEPT else "reject"
                vote_counts[d.bib_key][key] += 1
            accepted_bib_keys = {bk for bk, v in vote_counts.items() if v["accept"] > v["reject"]}

            n_accepted = n_done = n_queued = 0
            for work in s.works:
                if work.bib_key not in accepted_bib_keys:
                    pass
                elif work.bib_key in already_done:
                    n_done += 1
                else:
                    n_queued += 1
                    to_process[s.iteration].append(work)
            n_accepted = len(accepted_bib_keys)
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
        # Collect edges as (full_hash, full_hash) pairs; resolved to bib_keys after save_set.
        pending_edges: list[tuple[str, str]] = []  # (citing_fhash, cited_fhash)

        for iteration, works in sorted(to_process.items()):
            target_iteration = iteration + 1
            target_id = f"{target_iteration:02d}-{direction}"

            try:
                target_set = self.load_set(target_id)
                target_known_hashes: set[str] = {full_fingerprint(_work_ref(w)) for w in target_set.works}
                logger.info("Updating existing set %s", target_id)
            except FileNotFoundError:
                target_set = Set(
                    id=target_id,
                    kind=kind,
                    iteration=target_iteration,
                    works=[],
                )
                target_known_hashes = set()
                logger.info("Creating new set %s", target_id)

            new_works: list[Work] = []
            for work in works:
                source_fhash = full_fingerprint(_work_ref(work))
                full_to_bib_key.setdefault(source_fhash, work.bib_key)

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
                    ref_work_ref = _as_work_ref(ref)
                    ref_fhash = full_fingerprint(ref_work_ref)
                    ref_shash = short_fingerprint(ref_work_ref)

                    if kind == SetKind.BACKWARD:
                        pending_edges.append((source_fhash, ref_fhash))
                    else:
                        pending_edges.append((ref_fhash, source_fhash))

                    if ref_fhash in all_known_hashes or ref_fhash in target_known_hashes:
                        continue

                    if ref_shash in short_to_bib_key:
                        # Fuzzy match: same paper from different source — register new hash, skip
                        all_known_hashes.add(ref_fhash)
                        target_known_hashes.add(ref_fhash)
                        full_to_bib_key[ref_fhash] = short_to_bib_key[ref_shash]
                        continue

                    all_known_hashes.add(ref_fhash)
                    target_known_hashes.add(ref_fhash)
                    added += 1
                    new_works.append(_work_from_provider_result(ref))

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

        # Resolve full-hash edges to bib_key edges using the now-complete keys registry.
        final_full_to_bib_key = {fh: e.bib_key for fh, e in self.load_keys().items()}
        # Merge in any runtime-added mappings (fuzzy matches registered above)
        final_full_to_bib_key.update(full_to_bib_key)
        new_relations: list[Relation] = []
        for citing_fhash, cited_fhash in pending_edges:
            citing_key = final_full_to_bib_key.get(citing_fhash)
            cited_key = final_full_to_bib_key.get(cited_fhash)
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
            logger.info("%d new relation(s) saved to relations/", len(new_relations))
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
        existing = [d for d in existing if d.bib_key != decision.bib_key]
        existing.append(decision)
        yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in existing]}, path)

    def delete_researcher_decision(self, set_id: str, bib_key: str, researcher_id: str) -> None:
        path = self._researcher_decisions_path(set_id, researcher_id)
        data = yml.load(path) or {}
        existing = [Decision.model_validate(d) for d in data.get("decisions", [])]
        remaining = [d for d in existing if d.bib_key != bib_key]
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

    # --- bidding --------------------------------------------------------

    def bidding_path(self, set_id: str, researcher_id: str) -> Path:
        return self.set_dir(set_id).root / f"{BIDDING_PREFIX}{researcher_id}.yml"

    def load_biddings(self, set_id: str) -> list[Bidding]:
        set_dir = self.set_dir(set_id).root
        if not set_dir.exists():
            return []
        biddings: list[Bidding] = []
        for f in sorted(set_dir.glob(f"{BIDDING_PREFIX}*.yml")):
            researcher_id = f.stem[len(BIDDING_PREFIX):]
            data = yml.load(f) or {}
            biddings.append(Bidding(researcher_id=researcher_id, work_ids=list(data.get("work_ids") or [])))
        return biddings

    def save_bidding(self, set_id: str, bidding: Bidding) -> None:
        path = self.bidding_path(set_id, bidding.researcher_id)
        self.set_dir(set_id).root.mkdir(parents=True, exist_ok=True)
        yml.dump({"work_ids": sorted(bidding.work_ids)}, path)

    def add_work_to_bidding(self, set_id: str, researcher_id: str, work_id: str) -> Bidding:
        path = self.bidding_path(set_id, researcher_id)
        self.set_dir(set_id).root.mkdir(parents=True, exist_ok=True)
        data = yml.load(path) or {}
        work_ids: list[str] = list(data.get("work_ids") or [])
        if work_id not in work_ids:
            work_ids.append(work_id)
        yml.dump({"work_ids": sorted(work_ids)}, path)
        return Bidding(researcher_id=researcher_id, work_ids=work_ids)

    def remove_work_from_bidding(self, set_id: str, researcher_id: str, work_id: str) -> Bidding:
        path = self.bidding_path(set_id, researcher_id)
        data = yml.load(path) or {}
        work_ids = [w for w in (data.get("work_ids") or []) if w != work_id]
        yml.dump({"work_ids": work_ids}, path)
        return Bidding(researcher_id=researcher_id, work_ids=work_ids)

    def delete_researcher_biddings(self, researcher_id: str) -> None:
        for set_id in self.list_set_ids():
            path = self.bidding_path(set_id, researcher_id)
            if path.exists():
                path.unlink()

    def rename_researcher_biddings(self, old_id: str, new_id: str) -> None:
        for set_id in self.list_set_ids():
            old_path = self.bidding_path(set_id, old_id)
            if old_path.exists():
                data = yml.load(old_path) or {}
                yml.dump(data, self.bidding_path(set_id, new_id))
                old_path.unlink()

    # --- key registry ---------------------------------------------------

    def keys_path(self) -> Path:
        return self.root / KEYS_FILE

    def load_keys(self) -> dict[str, KeyEntry]:
        """Mapping of full_fingerprint -> KeyEntry(short, bib_key) for the whole project."""
        data = yml.load(self.keys_path()) or {}
        result: dict[str, KeyEntry] = {}
        for fhash, entry in (data.get("keys") or {}).items():
            result[fhash] = KeyEntry(short=entry["short"], bib_key=entry["bib_key"])
        return result

    def save_keys(self, keys: dict[str, KeyEntry]) -> None:
        serialized = {
            fhash: {"short": e.short, "bib_key": e.bib_key}
            for fhash, e in sorted(keys.items())
        }
        yml.dump({"keys": serialized}, self.keys_path())

    def _renormalize_keys(self, works: list[Work]) -> None:
        """Assign bib_keys and persist in keys.yml using the two-level fingerprint algorithm.

        1. Full fingerprint match → reuse existing bib_key (exact re-import).
        2. Short fingerprint match → reuse existing bib_key (same paper, different source).
        3. No match → mint new bib_key (<surname><year><word>, sequential suffix on collision).
        """
        keys = self.load_keys()
        short_to_bib_key: dict[str, str] = {e.short: e.bib_key for e in keys.values()}
        taken: set[str] = {e.bib_key for e in keys.values()}

        for work in works:
            ref = _work_ref(work)
            fhash = full_fingerprint(ref)
            shash = short_fingerprint(ref)

            if fhash in keys:
                work.bib_key = keys[fhash].bib_key
                continue

            if shash in short_to_bib_key:
                bk = short_to_bib_key[shash]
                keys[fhash] = KeyEntry(short=shash, bib_key=bk)
                work.bib_key = bk
                continue

            new_key = mint_bib_key(ref, taken)
            keys[fhash] = KeyEntry(short=shash, bib_key=new_key)
            short_to_bib_key[shash] = new_key
            taken.add(new_key)
            work.bib_key = new_key

        self.save_keys(keys)

    # --- relations ------------------------------------------------------

    def load_relations(self) -> list[Relation]:
        relations: list[Relation] = []
        seen: set[tuple[str, str]] = set()
        rdir = self.relations_dir()
        if not rdir.exists():
            return []
        for path in sorted(rdir.glob("*.yml")):
            bib_key = path.stem
            data = yml.load(path) or {}
            for cited in data.get("cite") or []:
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
        rdir = self.relations_dir()
        rdir.mkdir(parents=True, exist_ok=True)
        expected_files = {self.relation_path(bib_key) for bib_key in grouped}
        for old_path in rdir.glob("*.yml"):
            if old_path not in expected_files:
                old_path.unlink()
        for bib_key, connections in sorted(grouped.items()):
            yml.dump(
                {
                    "cite": sorted(set(connections["cite"])),
                    "cited_by": sorted(set(connections["cited_by"])),
                },
                self.relation_path(bib_key),
            )

    def _move_work(self, bib_key: str, from_set_id: str, to_set_id: str) -> None:
        """Move a work and its per-researcher decisions from one set to another."""
        from_set = self.load_set(from_set_id)
        to_set = self.load_set(to_set_id)

        work = next((w for w in from_set.works if w.bib_key == bib_key), None)
        if not work:
            return

        from_set.works = [w for w in from_set.works if w.bib_key != bib_key]
        to_set.works.append(work)
        self.save_set(from_set)
        self.save_set(to_set)

        from_dir = self.set_dir(from_set_id).root
        for dec_file in sorted(from_dir.glob(f"{DECISIONS_PREFIX}*.yml")):
            data = yml.load(dec_file) or {}
            all_dec = [Decision.model_validate(d) for d in data.get("decisions", [])]
            to_move = [d for d in all_dec if d.bib_key == bib_key]
            remaining = [d for d in all_dec if d.bib_key != bib_key]
            if remaining:
                yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in remaining]}, dec_file)
            else:
                dec_file.unlink()
            for d in to_move:
                self.save_researcher_decision(to_set_id, d)
        logger.info("Moved work %s from %s to %s", bib_key, from_set_id, to_set_id)

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
            if d.bib_key != source_work.bib_key:
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

        keys = self.load_keys()
        full_to_bib_key: dict[str, str] = {fh: e.bib_key for fh, e in keys.items()}
        short_to_bib_key: dict[str, str] = {e.short: e.bib_key for e in keys.values()}

        all_known: dict[str, tuple[Set, Work]] = {}  # bib_key → (set, work)
        for s in all_sets:
            for w in s.works:
                all_known[w.bib_key] = (s, w)

        try:
            target_set = self.load_set(target_id)
        except FileNotFoundError:
            target_set = Set(id=target_id, kind=kind, iteration=target_iteration, works=[])

        target_known_hashes: set[str] = {full_fingerprint(_work_ref(w)) for w in target_set.works}

        source_fhash = full_fingerprint(_work_ref(source_work))
        full_to_bib_key.setdefault(source_fhash, source_work.bib_key)

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
        pending_edges: list[tuple[str, str]] = []  # (citing_fhash, cited_fhash)
        moves: list[tuple[str, str]] = []  # (bib_key, from_set_id) to move into target

        for ref in refs:
            ref_work_ref = _as_work_ref(ref)
            ref_fhash = full_fingerprint(ref_work_ref)
            ref_shash = short_fingerprint(ref_work_ref)

            if kind == SetKind.BACKWARD:
                pending_edges.append((source_fhash, ref_fhash))
            else:
                pending_edges.append((ref_fhash, source_fhash))

            if ref_fhash in target_known_hashes:
                continue

            # Resolve bib_key for this ref
            ref_bib_key = full_to_bib_key.get(ref_fhash) or short_to_bib_key.get(ref_shash)

            if ref_bib_key and ref_bib_key in all_known:
                existing_set, _ = all_known[ref_bib_key]
                if existing_set.iteration > target_iteration:
                    moves.append((ref_bib_key, existing_set.id))
                    target_known_hashes.add(ref_fhash)
                    full_to_bib_key[ref_fhash] = ref_bib_key
            elif ref_fhash not in full_to_bib_key:
                target_set.works.append(_work_from_provider_result(ref))
                target_known_hashes.add(ref_fhash)

        already_done[bib_key] = {"at": now_iso, "found": len(refs)}
        self.save_set(target_set)
        self.save_snowball_log(log)

        moved_from_ids: list[str] = []
        for move_bib_key, from_set_id in moves:
            self._move_work(move_bib_key, from_set_id, target_id)
            if from_set_id not in moved_from_ids:
                moved_from_ids.append(from_set_id)

        final_full_to_bib_key = {fh: e.bib_key for fh, e in self.load_keys().items()}
        final_full_to_bib_key.update(full_to_bib_key)
        new_relations: list[Relation] = []
        for citing_fhash, cited_fhash in pending_edges:
            citing_key = final_full_to_bib_key.get(citing_fhash)
            cited_key = final_full_to_bib_key.get(cited_fhash)
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

    def _move_decisions_between(self, bib_key: str, from_set_id: str, to_set_id: str) -> None:
        from_dir = self.set_dir(from_set_id).root
        if not from_dir.exists():
            return
        for dec_file in sorted(from_dir.glob(f"{DECISIONS_PREFIX}*.yml")):
            data = yml.load(dec_file) or {}
            all_dec = [Decision.model_validate(d) for d in data.get("decisions", [])]
            to_move = [d for d in all_dec if d.bib_key == bib_key]
            remaining = [d for d in all_dec if d.bib_key != bib_key]
            if remaining:
                yml.dump({"decisions": [d.model_dump(mode="json", exclude_none=True) for d in remaining]}, dec_file)
            else:
                dec_file.unlink()
            for d in to_move:
                self.save_researcher_decision(to_set_id, d)

    def recalculate_orphans(self) -> None:
        """Rebalance backward/forward sets and the orphan set from the citation graph.

        A backward-set paper is connected iff some consensus-accepted paper cites it.
        A forward-set paper is connected iff it cites some consensus-accepted paper.
        Disconnected works move to the orphan set. Orphans that regain a connection
        return to the earliest valid iteration set (accepting_paper.iteration + 1
        with the matching kind), creating that set if needed.
        """
        regular_ids = [sid for sid in self.list_set_ids() if _SET_DIR_PATTERN.match(sid)]
        regular_sets = {sid: self.load_set(sid) for sid in regular_ids}

        accepted_bib_keys: set[str] = set()
        bib_key_iteration: dict[str, int] = {}
        for sid, s in regular_sets.items():
            decisions, _ = self.load_decisions(sid)
            votes: dict[str, dict[str, int]] = defaultdict(lambda: {"accept": 0, "reject": 0})
            for d in decisions:
                votes[d.bib_key]["accept" if d.verdict == Verdict.ACCEPT else "reject"] += 1
            for w in s.works:
                bib_key_iteration[w.bib_key] = s.iteration
                if votes[w.bib_key]["accept"] > votes[w.bib_key]["reject"]:
                    accepted_bib_keys.add(w.bib_key)

        relations = self.load_relations()
        cited_by_accepted = {r.cited_bib_key for r in relations if r.citing_bib_key in accepted_bib_keys}
        cites_accepted = {r.citing_bib_key for r in relations if r.cited_bib_key in accepted_bib_keys}

        orphan_id = "orphan"
        try:
            orphan_set = self.load_set(orphan_id)
        except FileNotFoundError:
            orphan_set = Set(id=orphan_id, kind=SetKind.ORPHAN, iteration=0, works=[])

        # Step 1: orphan disconnected works from regular backward/forward sets.
        existing_orphan_bib_keys = {w.bib_key for w in orphan_set.works}
        for sid, s in regular_sets.items():
            if s.kind == SetKind.BACKWARD:
                connected = cited_by_accepted
            elif s.kind == SetKind.FORWARD:
                connected = cites_accepted
            else:
                continue
            keep: list[Work] = []
            to_orphan: list[Work] = []
            for w in s.works:
                if w.bib_key in connected:
                    keep.append(w)
                else:
                    to_orphan.append(w)
            if not to_orphan:
                continue
            s.works = keep
            self.save_set(s)
            for w in to_orphan:
                if w.bib_key not in existing_orphan_bib_keys:
                    orphan_set.works.append(w)
                    existing_orphan_bib_keys.add(w.bib_key)
                self._move_decisions_between(w.bib_key, sid, orphan_id)
                logger.info("Orphaned work %s from %s", w.bib_key, sid)

        # Step 2: return reconnected orphans to the earliest valid iteration set.
        remaining_orphans: list[Work] = []
        for w in orphan_set.works:
            target = self._earliest_target_set_for_orphan(
                w.bib_key, accepted_bib_keys, bib_key_iteration, relations,
            )
            if target is None:
                remaining_orphans.append(w)
                continue
            target_id, target_kind, target_iter = target
            try:
                target_set = self.load_set(target_id)
            except FileNotFoundError:
                target_set = Set(id=target_id, kind=target_kind, iteration=target_iter, works=[])
            if w.bib_key not in {tw.bib_key for tw in target_set.works}:
                target_set.works.append(w)
                self.save_set(target_set)
                self._move_decisions_between(w.bib_key, orphan_id, target_id)
                logger.info("Returned work %s from orphan to %s", w.bib_key, target_id)

        orphan_set.works = remaining_orphans
        self.save_set(orphan_set)

    def _earliest_target_set_for_orphan(
        self,
        bib_key: str,
        accepted_bib_keys: set[str],
        bib_key_iteration: dict[str, int],
        relations: list[Relation],
    ) -> tuple[str, SetKind, int] | None:
        candidates: list[tuple[int, str]] = []  # (target_iteration, kind)
        for r in relations:
            if r.cited_bib_key == bib_key and r.citing_bib_key in accepted_bib_keys:
                it = bib_key_iteration.get(r.citing_bib_key)
                if it is not None:
                    candidates.append((it + 1, "backward"))
            if r.citing_bib_key == bib_key and r.cited_bib_key in accepted_bib_keys:
                it = bib_key_iteration.get(r.cited_bib_key)
                if it is not None:
                    candidates.append((it + 1, "forward"))
        if not candidates:
            return None
        candidates.sort()  # min iteration; "backward" < "forward" lexicographically
        it, kind = candidates[0]
        return f"{it:02d}-{kind}", SetKind(kind), it

    def _apply_group_decisions(
        self,
        set_id: str,
        works: list[Work],
        final_by_full: dict[str, str],
        criteria: list[Criterion] | None,
        phases: list[Phase] | None,
        researcher_id: str,
        active_phase: str | None = None,
    ) -> None:
        """Create/update decisions for works whose `groups` field matches a criterion or phase."""
        now = datetime.now(timezone.utc)

        if criteria:
            criterion_by_id = {c.id: c for c in criteria}
            for w in works:
                groups_raw = w.extra.get("groups", "")
                groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
                for group in groups:
                    if group in criterion_by_id:
                        c = criterion_by_id[group]
                        verdict = Verdict.ACCEPT if c.kind == "include" else Verdict.REJECT
                        final_bib_key = final_by_full.get(full_fingerprint(_work_ref(w)), w.bib_key)
                        existing_decisions, _ = self.load_decisions(set_id)
                        existing_phase_id = next(
                            (d.phase_id for d in existing_decisions
                             if d.bib_key == final_bib_key and d.researcher_id == researcher_id),
                            None,
                        )
                        decision = Decision(
                            bib_key=final_bib_key,
                            researcher_id=researcher_id,
                            verdict=verdict,
                            criterion_id=c.id,
                            phase_id=existing_phase_id,
                            note=None,
                            decided_at=now,
                        )
                        self.save_researcher_decision(set_id, decision)
                        break

        if phases:
            phase_by_id = {p.id: p for p in phases}
            current_decisions, _ = self.load_decisions(set_id)
            decisions_by_bib_key = {
                d.bib_key: d for d in current_decisions if d.researcher_id == researcher_id
            }
            for w in works:
                groups_raw = w.extra.get("groups", "")
                groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
                matched_phase_id: str | None = None
                for group in groups:
                    if group in phase_by_id:
                        matched_phase_id = phase_by_id[group].id
                        break
                if not matched_phase_id:
                    matched_phase_id = active_phase
                if not matched_phase_id:
                    continue
                final_bib_key = final_by_full.get(full_fingerprint(_work_ref(w)), w.bib_key)
                existing = decisions_by_bib_key.get(final_bib_key)
                if existing:
                    updated = existing.model_copy(update={"phase_id": matched_phase_id})
                    self.save_researcher_decision(set_id, updated)

    def import_bib_to_set(
        self,
        set_id: str,
        new_works: list[Work],
        criteria: list[Criterion] | None = None,
        phases: list[Phase] | None = None,
        researcher_id: str | None = None,
        active_phase: str | None = None,
    ) -> Set:
        """Add works from a BibTeX import to an existing set, deduplicating.

        If criteria/phases and researcher_id are provided, creates or updates
        decisions for works whose `groups` field matches a criterion or phase ID.
        Criteria matching sets the verdict; phase matching annotates the decision.
        """
        try:
            existing = self.load_set(set_id)
        except FileNotFoundError:
            raise ValueError(f"Set not found: {set_id}")

        # Build lookup indices for existing works using fingerprints and DOI.
        existing_by_full: dict[str, int] = {}
        existing_by_short: dict[str, int] = {}
        existing_by_doi: dict[str, int] = {}
        existing_by_bib_key: dict[str, int] = {}
        for i, w in enumerate(existing.works):
            ref = _work_ref(w)
            existing_by_full[full_fingerprint(ref)] = i
            existing_by_short[short_fingerprint(ref)] = i
            if doi := _normalized_doi(w):
                existing_by_doi[doi] = i
            existing_by_bib_key[w.bib_key] = i

        added: list[Work] = []
        for w in new_works:
            ref = _work_ref(w)
            fhash = full_fingerprint(ref)
            shash = short_fingerprint(ref)

            existing_index = existing_by_full.get(fhash)
            if existing_index is None and (doi := _normalized_doi(w)):
                existing_index = existing_by_doi.get(doi)
            if existing_index is None:
                existing_index = existing_by_short.get(shash)
            if existing_index is None:
                existing_index = existing_by_bib_key.get(w.bib_key)

            if existing_index is not None:
                current = existing.works[existing_index]
                merged = _fill_missing_work_fields(current, w)
                existing.works[existing_index] = merged
                merged_ref = _work_ref(merged)
                existing_by_full[full_fingerprint(merged_ref)] = existing_index
                existing_by_short[short_fingerprint(merged_ref)] = existing_index
                if doi := _normalized_doi(merged):
                    existing_by_doi[doi] = existing_index
            else:
                existing.works.append(w)
                added.append(w)
                new_index = len(existing.works) - 1
                existing_by_full[fhash] = new_index
                existing_by_short[shash] = new_index
                if doi := _normalized_doi(w):
                    existing_by_doi[doi] = new_index
                existing_by_bib_key[w.bib_key] = new_index
        self.save_set(existing)

        if researcher_id and (criteria or phases):
            # Reload to get finalized bib_keys after _renormalize_keys ran in save_set.
            final_set = self.load_set(set_id)
            final_by_full = {full_fingerprint(_work_ref(w)): w.bib_key for w in final_set.works}
            self._apply_group_decisions(
                set_id, new_works, final_by_full, criteria, phases, researcher_id, active_phase
            )

        return self.load_set(set_id)

    def import_unplaced_work(
        self,
        work: Work,
        criteria: list[Criterion] | None = None,
        phases: list[Phase] | None = None,
        researcher_id: str | None = None,
        active_phase: str | None = None,
    ) -> Work:
        """Import a work without a predetermined target set.

        The work is saved to the library. If it already exists in a regular set,
        decisions are applied there. Otherwise it is added to the orphan set.
        Does NOT call recalculate_orphans (callers do that after the full batch).
        """
        [merged] = self.merge_with_library([work])

        regular_ids = [sid for sid in self.list_set_ids() if _SET_DIR_PATTERN.match(sid)]
        found_set_id: str | None = None
        for sid in regular_ids:
            s = self.load_set(sid)
            if any(w.bib_key == merged.bib_key for w in s.works):
                found_set_id = sid
                break

        if found_set_id is None:
            # Also check by fingerprint in case bib_key isn't assigned yet
            ref = _work_ref(merged)
            fhash = full_fingerprint(ref)
            shash = short_fingerprint(ref)
            doi_norm = _normalized_doi(merged)
            for sid in regular_ids:
                s = self.load_set(sid)
                for w in s.works:
                    wr = _work_ref(w)
                    if (full_fingerprint(wr) == fhash
                            or short_fingerprint(wr) == shash
                            or (doi_norm and _normalized_doi(w) == doi_norm)):
                        found_set_id = sid
                        merged = _fill_missing_work_fields(w, merged)
                        break
                if found_set_id:
                    break

        if found_set_id:
            # Update the existing work in the regular set
            target_set = self.load_set(found_set_id)
            for i, w in enumerate(target_set.works):
                if w.bib_key == merged.bib_key:
                    target_set.works[i] = _fill_missing_work_fields(w, merged)
                    merged = target_set.works[i]
                    break
            self.save_set(target_set)
            if researcher_id and (criteria or phases):
                final_by_full = {full_fingerprint(_work_ref(w)): w.bib_key for w in target_set.works}
                self._apply_group_decisions(
                    found_set_id, [merged], final_by_full, criteria, phases, researcher_id, active_phase
                )
        else:
            # Stage as orphan
            orphan_id = "orphan"
            try:
                orphan_set = self.load_set(orphan_id)
            except FileNotFoundError:
                orphan_set = Set(id=orphan_id, kind=SetKind.ORPHAN, iteration=0, works=[])

            # Deduplicate within the orphan set
            ref = _work_ref(merged)
            fhash = full_fingerprint(ref)
            doi_norm = _normalized_doi(merged)
            existing_index: int | None = None
            for i, w in enumerate(orphan_set.works):
                wr = _work_ref(w)
                if (full_fingerprint(wr) == fhash
                        or (doi_norm and _normalized_doi(w) == doi_norm)):
                    existing_index = i
                    break
            if existing_index is not None:
                orphan_set.works[existing_index] = _fill_missing_work_fields(orphan_set.works[existing_index], merged)
                merged = orphan_set.works[existing_index]
            else:
                orphan_set.works.append(merged)
            self.save_set(orphan_set)

            if researcher_id and (criteria or phases):
                reloaded = self.load_set(orphan_id)
                final_by_full = {full_fingerprint(_work_ref(w)): w.bib_key for w in reloaded.works}
                self._apply_group_decisions(
                    orphan_id, [merged], final_by_full, criteria, phases, researcher_id, active_phase
                )

        return self.load_work(merged.bib_key) or merged

    # --- bootstrap ------------------------------------------------------

    def init(self, project: Project) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.save_project(project)
        self.ensure_scaffolding()
        for r in project.researchers:
            self.save_researcher(r)

    def ensure_scaffolding(self) -> None:
        """Idempotently create the directory layout and the empty start set."""
        self.sets_dir().mkdir(parents=True, exist_ok=True)
        self.works_dir().mkdir(parents=True, exist_ok=True)
        self.relations_dir().mkdir(parents=True, exist_ok=True)
        self.researchers_dir().mkdir(parents=True, exist_ok=True)
        if not self.set_dir("00-start").root.exists():
            self.save_set(Set(id="00-start", kind=SetKind.START, iteration=0, works=[]))

    def import_start_set(self, works: list[Work]) -> Set:
        start = Set(id="00-start", kind=SetKind.START, iteration=0, works=works)
        self.save_set(start)
        return start
