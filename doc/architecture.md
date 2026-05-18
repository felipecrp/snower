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
      orphans.py              # POST /api/orphans/recalculate
  domain/
    models.py                 # Pydantic models (Work, Set, Decision, …)
    identity.py               # work_id(), mint_bib_key(), normalization helpers
  storage/
    repo.py                   # ProjectRepo: all read/write operations
    bib.py                    # BibTeX ↔ Work conversion
    yml.py                    # ruamel.yaml wrapper (block style)
  providers/
    base.py                   # Provider ABC
    factory.py                # get_provider() for snowballing; get_enrichment_provider() (always OpenAlex)
    scholarly_provider.py     # Google Scholar via `scholarly`
    openalex_provider.py      # OpenAlex (default snowballing + import enrichment)
    semantic_scholar_provider.py
ui/                           # Angular SPA
electron/
  main.js                     # Electron main process
```

## On-disk Project Layout

```
<project>/
  project.yml          # name, researchers, criteria, providers
  keys.yml             # global registry: {bib_key: work_id}
  snowballing.yml      # timestamps: {direction: {bib_key: {at, found}}}
  relations/           # per-paper citation graph files
    wohlin2014snowballingsystematic.yml
    ...
  works/               # per-paper BibTeX library, shared across all sets
    wohlin2014snowballingsystematic.bib
    ...
  sets/
    00-start/
      set.yml          # {id, kind, iteration, works: [bib_key, ...]}
      decisions_<researcher_id>.yml
      resolutions.yml
    01-backward/
      set.yml
      ...
    orphan/
      set.yml          # same structure; papers disconnected from the graph
```

### Work library (`works/`)

Each paper is stored once as `works/<bib_key>.bib`, shared across every set that lists it in its `set.yml`. Updating a `.bib` file is immediately reflected in all sets.

**Import enrichment**: `get_enrichment_provider()` always returns `OpenAlexProvider`. At import the flow is:
1. `repo.merge_with_library(incoming)` — fills gaps from the cached `.bib` so already-enriched papers skip the network.
2. `OpenAlexProvider.enrich_works(works)` — short-circuits if all fields are present; otherwise fills missing fields (abstract, venue, URL, DOI) without overwriting existing values.
3. `repo.import_bib_to_set()` / `repo.import_start_set()` — persists to `works/` and updates the set manifest.

## Orphan Sets

When a consensus-accepted paper gets rejected, backward/forward papers that depended on it may lose their connection to the review corpus and become orphans.

**Orphaning rule:**
- A backward-set paper is orphaned when no consensus-accepted paper cites it (via `relations/`).
- A forward-set paper is orphaned when it cites no consensus-accepted paper.

**Return rule:** When an orphan regains a connection, it returns to the **earliest valid iteration set** — specifically the set at `accepting_paper.iteration + 1` with the matching kind (`backward`/`forward`). The target set is created if it does not yet exist.

**Implementation:** `recalculate_orphans()` in `repo.py` fully recomputes membership from `relations/` + current consensus on every call. No per-paper origin/direction metadata is stored. The orphan `set.yml` has the same `works: [bib_key, ...]` structure as any other set. Decisions for moved papers are migrated alongside them.

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
