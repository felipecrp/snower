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
  "sets": [
    { "name": "start", "round": 0, "count": 1 }
  ]
}
```

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
  "included": true
}
```

**Errors** `404` if the paper does not exist.

---

#### `PATCH /papers/{bib_id}`

Include or exclude a paper (screening). Excluded papers keep their set/round assignment but stop propagating placement to their neighbours.

**Request body**
```json
{ "included": false }
```

**Response** `200 Paper` — the updated paper.

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

## Out of scope

The following operations are intentionally not exposed by this API version:

- Add-edge endpoints (recording references/citations)
- Paper-neighbour traversal endpoints

The citation graph grows only via seeds and edges already present on disk; the API screens and reads it.
