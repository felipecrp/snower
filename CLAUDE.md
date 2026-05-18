# Snow — Context for Claude

Snow is a local-first systematic literature review tool using the Wohlin snowballing method. All data is stored as BibTeX + YAML files, versionable with git. The server runs on `127.0.0.1`; no data leaves the machine.

## Instructions

-  Ask permission before spawning agents

## Stack

- **Backend:** Python 3.13, FastAPI, Pydantic v2, bibtexparser 1.4.4, ruamel.yaml, scholarly, Typer/Uvicorn
- **Frontend:** Angular 21, standalone components, signals (no NgRx/services for state)
- **Desktop:** Electron (dev mode only — loads `http://localhost:4200`)
- **Tests:** pytest + pytest-pyspec (`Describe*` / `it_*` naming)
- **Package managers:** `uv` for Python, `npm` for JS. Never edit pyproject.toml or package.json by hand.

## Running the project

```bash
# Backend
uv run snow serve --project <project-dir>

# Frontend
cd ui && npm run start

# Electron dev window
cd ui && npm run electron:dev

# Tests
uv run pytest
```

## Key Conventions

- **All business logic in Python.** Angular is a pure UI layer that calls the local API.
- **Criterion drives verdict.** No accept/reject buttons; selecting an `include` criterion → `accept`, `exclude` → `reject`.
- **Tests alongside modules**, not in a batch at the end. Test tree mirrors `snow/` hierarchy under `tests/`.
- **English for code**, Portuguese for conversation.
- **Explain before non-trivial edits.**

## Project Layout

See `doc/architecture.md` for the full module tree and on-disk storage layout.

Key entry points:
- `snow/storage/repo.py` — `ProjectRepo`, all disk I/O
- `snow/domain/identity.py` — `work_id()`, `mint_bib_key()`
- `snow/providers/factory.py` — `get_provider()` for snowballing; `get_enrichment_provider()` (always OpenAlex, used at import)

## Data Identity

Every paper has a stable `work_id = sha1:<hex16>` derived from `surname|year|title` (Unicode-normalized). DOI is metadata only. BibTeX keys follow `<surname><year><slug>`; the global registry is `keys.yml`. See `doc/data-model.md` for details.

## Snowballing Logic

- Papers from iteration N feed into iteration N+1.
- `POST /api/snowballing/{backward|forward}` is the global trigger.
- Papers already in `snowballing.yml` are skipped.
- Default enrichment provider: OpenAlex (fills missing fields at import without overwriting existing ones).

## Orphan Sets

Backward/forward papers that lose their connection to the consensus-accepted graph move to `sets/orphan/`. Orphans return to the earliest valid iteration set when they regain a connection. Membership is recomputed from `relations/` + consensus on every call to `recalculate_orphans()`. See `doc/architecture.md` for details.

## Multi-researcher

- Active researcher chosen from dropdown in topbar; stored in `localStorage`.
- `X-Researcher-Id` header on PUT/DELETE decision requests.
- Renaming a researcher id via `PUT /api/project/researchers` with `previous_id` rewrites all decisions.
- Removing a researcher deletes all their decisions across all sets.

## Results / Consensus

- "Results (consensus)" option in the "View as" dropdown.
- Paper is `accept` if `accept_count > reject_count` across all researchers; `reject` if the reverse.
- Ties and papers with no votes are hidden.
- Sidebar shows `X/Y` (consensus-accepted / total) per set.

## What's Not Implemented Yet

- Packaged Electron distribution (dev mode only)
- Formal resolution UI (Resolution model exists but is not exposed in the UI)
- Proxy configuration for scholarly (needed for large batches)
- Export to consolidated `.bib` of accepted papers
