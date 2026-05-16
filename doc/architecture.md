# Architecture

## Module Layout

```
snow/
  cli.py                      # Entry point: init, import-bib, serve
  api/
    app.py                    # FastAPI factory, CORS, router registration
    state.py                  # Dependency injection (repo, active researcher)
    routers/
      project.py              # GET /api/project, PUT researchers/criteria
      sets.py                 # GET /api/sets, GET /api/sets/{id}, POST snowballing per-set
      decisions.py            # GET/PUT/DELETE /api/sets/{id}/decisions/{work_id}
      snowballing.py          # POST /api/snowballing/{kind} (global)
  domain/
    models.py                 # Pydantic models (Work, Set, Decision, …)
    identity.py               # work_id(), mint_bib_key(), normalization helpers
  storage/
    repo.py                   # ProjectRepo: all read/write operations
    bib.py                    # BibTeX ↔ Work conversion
    yml.py                    # ruamel.yaml wrapper (block style)
  providers/
    base.py                   # Provider ABC
    scholarly_provider.py     # Google Scholar via `scholarly`
ui/                           # Angular SPA
electron/
  main.js                     # Electron main process
```

## Design Principles

### All logic in Python
The Angular frontend is a pure UI layer. It only renders data and calls the local API. Business rules (deduplication, consensus, snowballing coordination, rename propagation) live exclusively in the Python backend. This makes the backend independently testable and means the UI can be replaced without touching any logic.

### Local-first, single process
The FastAPI server runs on `127.0.0.1:8000`. Electron loads `http://localhost:4200` (Angular dev server), which proxies `/api/*` calls to FastAPI. There is no cloud component; everything is on the researcher's machine.

### Git as the collaboration layer
Multiple researchers can work on the same project by cloning a git repository, working on separate branches, and merging. There is no authentication: the active researcher is chosen in the UI and stored in browser localStorage. Trust is social (via git authorship and branch history).

## Dependency Injection

`snow/api/state.py` exposes two FastAPI dependencies:

- `get_repo` — returns a `ProjectRepo` bound to the project directory stored in `app.state.snow`.
- `get_active_researcher` — reads the `X-Researcher-Id` request header and validates it against the project's researcher list. Returns 401 if missing, 403 if unknown.

## Testing Strategy

Tests use `pytest-pyspec` with the `Describe*` / `it_*` naming convention. The test tree mirrors the source tree:

```
tests/
  domain/test_identity.py
  storage/test_bib.py
  storage/test_repo.py
  api/conftest.py          # TestClient fixture with a temp project dir
  api/test_project.py
  api/test_sets.py
  api/test_decisions.py
```

The API tests use `fastapi.testclient.TestClient` with a real `ProjectRepo` backed by a temporary directory populated in `conftest.py`. No mocking of the storage layer.
