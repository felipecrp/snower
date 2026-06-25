# Snower REST API

The Snower API exposes the SLR snowballing engine over HTTP so a UI can drive it. The server is single-project: you point it at a project directory on startup and every route operates on that project.

## Running the server

```bash
SNOWER_PROJECT_PATH=./my-review uv run uvicorn snower.api.app:app --reload
```

If the directory does not contain a project yet, the server creates one automatically. Interactive docs are available at `http://localhost:8000/docs`.

## Configuration

| Environment variable  | Default     | Purpose                            |
|-----------------------|-------------|------------------------------------|
| `SNOWER_PROJECT_PATH` | `./project` | Path to the project directory      |

## Autosave

Every mutating request (import, screening, add seed) saves the project to disk automatically. There is no explicit save endpoint.

## Endpoints

### Project

#### `GET /`

Get a summary of the current project.

**Response** `200 ProjectSummary`

```json
{
  "name": "my-review",
  "seeds": ["kitchenham2009systematic"],
  "sets": [{ "name": "start", "round": 0, "count": 1 }],
  "criteria": [{ "id": "ic1", "name": "Peer reviewed", "type": "inclusion" }],
  "phases": [{ "id": "title", "name": "Title screening" }],
  "researchers": [{ "email": "a@b.com", "name": "Ana" }]
}
```

---

#### `PATCH /`

Update project-level settings.

**Request body**
```json
{ "decision_strategy": "consensus" }
```

Valid values: `"majority"` (default), `"consensus"`. Switching strategy recomputes every paper's decision from its reviews and re-derives snowball placement. See [doc/decision.md](decision.md).

**Response** `200 ProjectSummary`

---

#### `GET /sets`

List all paper sets derived from the citation graph.

**Response** `200 list[PaperSet]`

```json
[
  { "name": "start", "round": 0, "paper_ids": ["kitchenham2009systematic"] }
]
```

---

#### `GET /sets/{set_name}/papers`

List papers in a named set. `set_name` is in the form `{direction}-{round}` (e.g. `start-0`, `backward-1`, `orphan--1`).

**Response** `200 list[Paper]`

---

#### `POST /import`

Import papers from a BibTeX string.

**Request body**
```json
{
  "bibtex": "@article{...}",
  "as_seed": false
}
```

- `as_seed: true` — registers each imported paper as a seed (placed at `start-0`).
- `as_seed: false` — adds papers to the pool as orphans; they gain a set only when an edge connects them to a seed.

Papers whose `bib_id` cannot be computed (missing author, year, or title) are reported in `skipped`.

**Response** `200 ImportResult`
```json
{
  "imported": ["kitchenham2009systematic"],
  "skipped": ["A paper without author or year"]
}
```

---

### Papers

#### `GET /papers`

List all papers in the project.

**Response** `200 list[Paper]`

---

#### `GET /papers/{bib_id}`

Get a single paper.

**Response** `200 Paper`

```json
{
  "bib_id": "kitchenham2009systematic",
  "title": "Systematic literature reviews in software engineering",
  "authors": [{ "family": "Kitchenham", "given": "Barbara", "suffix": null }],
  "year": 2009,
  "decision": "undecided"
}
```

**Errors** `404` if the paper does not exist.

---

#### `PATCH /papers/{bib_id}`

Record a researcher's screening assessment for a paper. The include/reject meaning is **derived** from the chosen criterion's `type`; it is not sent in the body.

**Request body**
```json
{
  "criterion_id": "ic1",
  "phase_id": "title",
  "researcher_email": "a@b.com"
}
```

**Response** `200 dict[email, Assessment]` — the paper's full assessment map after recording.

**Errors**
- `404` if the paper, criterion, phase, or researcher does not exist.

---

#### `GET /papers/{bib_id}/assessments`

Get all researcher assessments for a paper.

**Response** `200 dict[email, Assessment]`

```json
{
  "a@b.com": {
    "criterion": {"id": "ic1", "name": "Peer reviewed", "type": "inclusion"},
    "phase": {"id": "title", "name": "Title screening"}
  }
}
```

**Errors** `404` if the paper does not exist.

---

#### `POST /papers/{bib_id}/seed`

Mark an existing paper as a seed. The paper must already be in the project. This is idempotent.

**Response** `200 ProjectSummary` — the updated project.

**Errors** `404` if the bib_id does not exist.

---

#### `DELETE /papers/{bib_id}/seed`

Remove a paper from seeds. The paper stays in the project and is re-placed via the citation graph (or becomes an orphan).

**Response** `200 ProjectSummary` — the updated project.

**Errors** `404` if the bib_id does not exist or the paper is not currently a seed.

---

### Review — Criteria, Phases, Researchers

#### `GET /criteria` · `POST /criteria` · `PATCH /criteria/{id}` · `DELETE /criteria/{id}`

CRUD for inclusion/exclusion criteria.

- `POST` body: `{"id": "ic1", "name": "Peer reviewed", "type": "inclusion"}` → `201`
- `PATCH` body: same shape; path `id` is authoritative → `204`
- `DELETE` → `204`
- `POST` returns `409` on duplicate id; `PATCH`/`DELETE` return `404` if absent.

#### `GET /phases` · `POST /phases` · `PATCH /phases/{id}` · `DELETE /phases/{id}`

CRUD for reading phases.

- `POST` body: `{"id": "title", "name": "Title screening"}` → `201`
- `PATCH` body: same shape; path `id` is authoritative → `204`
- `DELETE` → `204`
- `POST` returns `409` on duplicate id; `PATCH`/`DELETE` return `404` if absent.

#### `GET /researchers` · `POST /researchers` · `PATCH /researchers/{email}` · `DELETE /researchers/{email}`

CRUD for researchers.

- `POST` body: `{"email": "a@b.com", "name": "Ana"}` → `201`
- `PATCH` body: same shape; path `email` is authoritative → `204`
- `DELETE` → `204`
- `POST` returns `409` on duplicate email; `PATCH`/`DELETE` return `404` if absent.

---

## Out of scope

The following operations are intentionally not exposed by this API version:

- Add-edge endpoints (recording references/citations)
- Paper-neighbour traversal endpoints

The citation graph grows only via seeds and edges already present on disk; the API screens and reads it.
