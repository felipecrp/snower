# API Reference

The FastAPI server runs at `http://127.0.0.1:8000`. Interactive docs are available at `/docs` (Swagger UI) when the server is running.

All endpoints return JSON. Errors follow the standard FastAPI format: `{"detail": "..."}`.

---

## Project

### `GET /api/project`
Returns the project configuration.

**Response:** `Project` object with `name`, `researchers`, `criteria`.

---

### `PUT /api/project/researchers`
Replaces the full researcher list.

**Body:** array of `ResearcherInput`
```json
[
  { "id": "alice", "name": "Alice Smith", "email": "alice@example.com" },
  { "id": "bob",   "name": "Bob Jones" }
]
```

**Rename support:** include `"previous_id": "<old_id>"` to rename a researcher. The backend rewrites `researcher_id` in all `decisions.yml` files and `by` in all `resolutions`.

**Remove behaviour:** researchers absent from the new list (and not renamed) have all their decisions deleted from every set.

---

### `PUT /api/project/criteria`
Replaces the full criterion list. Same rename mechanics as researchers (`previous_id` rewrites `criterion_id` in decisions).

---

## Sets

### `GET /api/sets`
Returns all sets (sorted by id), each with their full `works` list.

### `GET /api/sets/{set_id}`
Returns one set. Returns `400` for malformed ids, `404` if not found.

### `POST /api/sets/{set_id}/snowballing/{kind}`
Creates an empty next-iteration set (`backward` or `forward`) parented to `{set_id}`. Returns the new `Set`. Returns `400` for `kind=start`.

---

## Decisions

All decision endpoints require the `X-Researcher-Id` header (PUT and DELETE).

### `GET /api/sets/{set_id}/decisions`
Returns `{ "decisions": [...], "resolutions": [...] }` for the set.

### `PUT /api/sets/{set_id}/decisions/{work_id}`
Upserts a decision for the active researcher. The `work_id` may contain `/` (URL-encoded as `%2F`).

**Headers:** `X-Researcher-Id: <researcher_id>`

**Body:** `DecisionInput`
```json
{ "verdict": "accept", "criterion_id": "inc1", "note": "Relevant" }
```

### `DELETE /api/sets/{set_id}/decisions/{work_id}`
Removes the active researcher's decision for the work.

**Headers:** `X-Researcher-Id: <researcher_id>`

---

## Snowballing

### `POST /api/snowballing/{kind}`
Triggers **global** backward or forward snowballing. Processes all accepted papers across all sets that have not been snowballed in the requested direction yet.

**Logic:**
1. Collects accepted papers (any `accept` decision) not yet in `snowballing.yml` for the given direction.
2. Groups them by their set's `iteration` N.
3. For each group, fetches references (backward) or citations (forward) via the configured provider (Google Scholar by default).
4. Creates or updates the set at `iteration N+1` with deduplicated new papers.
5. Records timestamps in `snowballing.yml`.

**Response:** array of `Set` objects that were created or updated.

**Note:** Uses the `scholarly` library which scrapes Google Scholar. Rate limits and CAPTCHA may apply for large batches.
