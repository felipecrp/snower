# Snow — Context for Claude

Snow is a local-first systematic literature review tool using the Wohlin snowballing method. All data is stored as BibTeX + YAML files, versionable with git. The server runs on `127.0.0.1`; no data leaves the machine.

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

## Project File Layout

```
snow/                  # Python package
  cli.py               # snow init / import-bib / serve
  api/
    app.py             # FastAPI factory
    routers/           # project.py, sets.py, decisions.py, snowballing.py
    state.py           # get_repo, get_active_researcher dependencies
  domain/
    models.py          # Work, Set, Decision, Resolution, Relation, Project, …
    identity.py        # work_id(), mint_bib_key()
  storage/
    repo.py            # ProjectRepo (all disk I/O)
    bib.py             # BibTeX ↔ Work
    yml.py             # ruamel.yaml wrapper
  providers/
    base.py            # Provider ABC
    scholarly_provider.py  # Google Scholar via scholarly
ui/                    # Angular SPA
  src/app/
    models.ts          # TypeScript interfaces mirroring Python models
    api.service.ts     # HTTP client
    triage/            # Main screen
    settings/          # Researcher + criteria management
electron/main.js       # Electron main process
tests/                 # Mirrors snow/ hierarchy
doc/                   # Project documentation
```

## Data Identity

Every paper gets a stable `work_id`:
1. `doi:<normalized>` when DOI is available (authoritative, URL-prefix stripped, lowercased)
2. `sha1:<hex16>` of `surname|year|title` (Unicode-normalized, diacritics removed)

BibTeX keys follow `<surname><year><letter>` (e.g. `wohlin2014a`). The global registry is `keys.yml`.

## Snowballing Logic

- Papers from sets at **iteration N** feed into sets at **iteration N+1**.
- `POST /api/snowballing/{backward|forward}` is the global trigger.
- It skips papers already logged in `snowballing.yml` for that direction.
- Provider: `ScholarlyProvider` (Google Scholar scraping — CAPTCHA risk on large batches).

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

## API Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/project` | Project config |
| PUT | `/api/project/researchers` | Replace researcher list (rename via `previous_id`) |
| PUT | `/api/project/criteria` | Replace criterion list |
| GET | `/api/sets` | All sets with works |
| GET | `/api/sets/{id}` | Single set |
| POST | `/api/sets/{id}/snowballing/{kind}` | Create empty next-iteration set |
| GET | `/api/sets/{id}/decisions` | All decisions + resolutions for a set |
| PUT | `/api/sets/{id}/decisions/{work_id}` | Upsert decision (needs X-Researcher-Id) |
| DELETE | `/api/sets/{id}/decisions/{work_id}` | Delete decision (needs X-Researcher-Id) |
| POST | `/api/snowballing/{kind}` | Global snowballing (fetches refs/citations for all unprocessed accepted papers) |

## What's Not Implemented Yet

- Packaged Electron distribution (dev mode only)
- Formal resolution UI (Resolution model exists but is not exposed in the UI)
- Additional providers (Semantic Scholar, OpenAlex)
- Proxy configuration for scholarly (needed for large batches)
- Export to consolidated `.bib` of accepted papers
