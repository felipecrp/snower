# Snow — Feature Catalog

Three-level hierarchy grouped by **product area**. Optional "Notes:" entries describe non-obvious behaviour.

---

## 1. Workspace & Project lifecycle

### 1.1 Create new project
Bootstrap a new project directory with default criteria (9 entries), git user as the first researcher, and an empty `00-start` set.

### 1.2 Open existing project
Bind the server to an already-initialised project directory; auto-creates `00-start` if missing.

- Notes: The workspace dialog is shown automatically when no project is open.

### 1.3 Recent projects list
Persist and recall the list of previously opened project directories.

### 1.4 Project metadata
Read and update project name and description.

---

## 2. Researchers & access control

### 2.1 Researcher CRUD
Add, rename, or remove researchers. Removing cascades deletes to all their decisions across every set.

- Notes: Rename rewrites `researcher_id` in all `decisions/` YAML files and all `bidding/` files.

### 2.2 Active researcher selection
Choose which researcher's perspective is applied to decisions. Selection is persisted in `localStorage`.

### 2.3 `X-Researcher-Id` header
All decision PUT/DELETE requests carry the active researcher's id in this header; 403 if the researcher is unknown.

- Notes: Decisions for all researchers are fetched together; the UI filters by the active researcher.

### 2.4 Git user auto-sync
Reads git global `user.name` / `user.email` to pre-populate the researcher identity.

---

## 3. Criteria & phases

### 3.1 Include/exclude criteria CRUD
Manage the list of selection criteria; each has an `id`, `description`, and `kind` (include/exclude).

- Notes: Saved list is sorted — include before exclude, then by `id`.

### 3.2 Review phases CRUD
Manage named review phases (e.g. "Title/Abstract", "Full Text"). Renaming a phase propagates the new id to all decisions.

### 3.3 Criterion-drives-verdict rule
There are no accept/reject buttons. Selecting an `include` criterion sets `verdict=accept`; selecting an `exclude` criterion sets `verdict=reject`.

---

## 4. Sets & imports

### 4.1 List / get sets
Enumerate all sets (start, backward/forward iterations, orphan) or fetch a single set by id.

### 4.2 BibTeX file upload
Upload a `.bib` file to a specific set.

### 4.3 Paste BibTeX / CSV / TSV
Parse raw pasted text and preview the resulting works before importing; supports BibTeX, CSV, and TSV formats.

### 4.4 Single-work import & unplaced staging
Import a single work from the UI; works with no valid set land in `sets/orphan/` until manually placed.

### 4.5 OpenAlex enrichment at import
Non-destructively fills missing fields (abstract, DOI, venue, …) from OpenAlex when works are imported.

- Notes: Never overwrites existing fields. Always uses OpenAlex regardless of the project's snowballing provider setting.

### 4.6 Edit raw BibTeX per paper
Open a modal with the raw `.bib` entry for a paper and save edits; preserved through subsequent imports.

---

## 5. Triage (decisions)

### 5.1 Per-researcher decisions
Each researcher records an independent verdict, criterion, phase, and note for each paper.

### 5.2 Filter by verdict / assignment
Show only accepted / rejected / undecided papers, or only papers assigned to the active researcher ("assigned to me").

### 5.3 Sort papers
Sort the paper list by author, title, venue, or criterion.

### 5.4 Verdict perspective toggle
Switch the displayed verdict between "My decisions" (active researcher) and "Majority" (consensus result).

### 5.5 Consensus rule
Majority accept > majority reject; ties resolve to undecided.

### 5.6 Keyboard shortcuts
Navigate and decide without a mouse: `Shift+H/L` moves between papers; `f+a/r/u/f` sets verdict (accept/reject/undecided/full-text phase).

- Notes: See `doc/shortcuts.md` for the full list.

---

## 6. Snowballing

### 6.1 Global backward / forward
Fetch references (backward) or citing papers (forward) for all consensus-accepted papers in the most recent iteration.

### 6.2 Per-paper snowball
Run backward or forward snowballing for a single paper identified by `bib_key`.

### 6.3 Skip already-snowballed papers
Papers already snowballed are not re-fetched unless `force=true`.

### 6.4 Force re-run
Pass `force=true` to bypass the cache and re-fetch from the provider.

### 6.5 Iteration progression
Backward/forward results land in sets named `{N+1}-backward` / `{N+1}-forward`, where N is the highest existing iteration number.

---

## 7. Orphan sets

### 7.1 Auto-evict disconnected children
Backward/forward papers whose source paper was later rejected (consensus) are moved to `sets/orphan/`.

### 7.2 Auto-return on reconnect
An orphaned paper returns to its earliest valid iteration set when its source paper is re-accepted.

### 7.3 Manual recalculation
Trigger orphan recomputation explicitly (e.g. after bulk decision changes).

---

## 8. Bidding (work assignment)

### 8.1 Per-paper bid / unbid
The active researcher bids on a paper to signal intent to review it; unbid removes the bid.

### 8.2 Per-researcher assignment percentage
Each researcher has an `assignment_percentage` (0–100) controlling their share of auto-assigned papers.

### 8.3 Fair-share auto-assignment
Distribute all unassigned papers across researchers proportionally by their assignment percentages.

- Notes: Existing bids are preserved; only unassigned papers are touched.

### 8.4 Cascade on researcher rename / remove
Bidding files are renamed when a researcher is renamed, and deleted when a researcher is removed.

---

## 9. Results & reporting

### 9.1 Consensus summary
Count of accepted / rejected / undecided papers across all sets using the consensus rule.

### 9.2 Iteration breakdown
Per-set paper counts and acceptance rate, visualising progress across iterations.

### 9.3 Accepted papers grouped by kind
Results view lists consensus-accepted papers grouped by BibTeX entry type.

### 9.4 Snow-Log
Per-paper log of snowballing events — which papers were snowballed, when, and which children were produced.

---

## 10. Persistence & local-first

### 10.1 BibTeX + YAML on-disk schema
All project state is stored as plain `.bib` and `.yml` files, versionable with git. No database.

### 10.2 Shared works library
Each paper is stored once; sets reference papers by `bib_key`.

### 10.3 Keys registry
Maps fingerprints to canonical `bib_key`s; sorted by fingerprint for deterministic diffs.

### 10.4 Relations
Stores parent → child edges for the snowballing graph.

### 10.5 Localhost-only server
The server binds to `127.0.0.1` by default; no data leaves the machine.

---

## 11. Downloads

### 11.1 Serve cached PDF inline
Stream a locally cached PDF file for a given paper, for in-browser preview.

---

## 12. CLI

### 12.1 `snow serve`
Start the server on `127.0.0.1:8000` (configurable via `--host` / `--port`). Verifies git identity before starting. Pass `--port 0` to bind to an OS-assigned free port.

### 12.2 `snow init <path>`
Bootstrap a new project directory with default structure. Equivalent to the UI "New project" flow but headless.

### 12.3 `snow import-bib <file>`
Import a `.bib` file as the project's `00-start` set; validates BibTeX format, enriches via OpenAlex, and writes to disk.
