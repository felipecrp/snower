# Data Model

## Domain Models (`snow/domain/models.py`)

### Work
A bibliographic entry as it appears inside a set.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Stable `work_id` (see Identity below) |
| `bib_key` | `str` | BibTeX key, e.g. `wohlin2014a` |
| `title` | `str` | |
| `authors` | `list[str]` | Each entry is `"Last, First"` or `"First Last"` |
| `year` | `int \| None` | |
| `venue` | `str \| None` | Journal or conference name |
| `doi` | `str \| None` | Normalized (lowercase, no URL prefix) |
| `url` | `str \| None` | |
| `abstract` | `str \| None` | |
| `extra` | `dict[str, str]` | Unknown BibTeX fields pass through |
| `last_backward_snowballed_at` | `datetime \| None` | Set by `run_global_snowballing` |
| `last_forward_snowballed_at` | `datetime \| None` | Set by `run_global_snowballing` |

### Set
One iteration of the snowballing process.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Pattern: `NN-kind`, e.g. `00-start`, `01-backward`, or `orphan` |
| `kind` | `SetKind` | `start`, `backward`, `forward`, or `orphan` |
| `iteration` | `int` | 0 for start, 1 for first round, etc. |
| `works` | `list[Work]` | Papers in this set (loaded from `works/<bib_key>.bib`) |

### Decision
A single researcher's triage verdict for one paper in one set.

| Field | Type | Notes |
|---|---|---|
| `work_id` | `str` | References `Work.id` |
| `researcher_id` | `str` | References `Researcher.id` |
| `verdict` | `Verdict` | `accept` or `reject` |
| `criterion_id` | `str \| None` | References `Criterion.id` |
| `note` | `str \| None` | Free text justification |
| `decided_at` | `datetime` | UTC timestamp |

### Resolution
A final decision when researchers disagreed (stored alongside decisions).

| Field | Type | Notes |
|---|---|---|
| `work_id` | `str` | |
| `verdict` | `Verdict` | |
| `by` | `str` | Researcher id or `"vote"` for automatic majority |
| `note` | `str \| None` | |
| `resolved_at` | `datetime` | |

### Relation
A directed citation edge between two works (stored in `relations/<bib_key>.yml`).

| Field | Type |
|---|---|
| `citing_work_id` | `str` |
| `cited_work_id` | `str` |

### Researcher / Criterion / Project
Stored in `project.yml`. `Criterion.kind` is `include` or `exclude` and determines the verdict when the researcher selects it (no separate Accept/Reject buttons in the UI).

---

## Work Identity (`snow/domain/identity.py`)

Every work gets a stable `work_id` computed deterministically:

1. **DOI available** → `doi:<normalized>` (lowercase, URL prefix stripped).
   Example: `doi:10.1145/3180155.3180238`
2. **No DOI** → `sha1:<hex16>` where the digest is SHA-1 of `surname|year|title` (all normalized: Unicode NFKD-folded, diacritics stripped, non-alphanumeric removed).
   Example: `sha1:3f4a9c1d2b7e0812`

The same paper appearing in multiple sets always gets the same `work_id`, enabling deduplication without a central registry.

---

## BibTeX Key Registry (`keys.yml`)

When works are written to disk, each gets a human-readable BibTeX key following the pattern `<surname><year><letter>` (e.g. `wohlin2014a`). The `keys.yml` file at the project root is the global registry mapping `bib_key → work_id`:

```yaml
keys:
  wohlin2014a: doi:10.1145/2601248.2601268
  kitchenham2007a: sha1:3f4a9c1d2b7e0812
```

- On first sight, `mint_bib_key` assigns the next available letter suffix (`a..z`, then `aa..zz`).
- On reload, the registry ensures each work always gets the same key, even across sets.
- Renaming a researcher or criterion via the settings screen propagates the new id to all `decisions.yml` files automatically.

---

## Snowball Log (`snowballing.yml`)

Records when each paper was snowballed, keyed by `work_id`:

```yaml
backward:
  doi:10.1145/3180155.3180238: "2024-06-01T14:32:00+00:00"
forward:
  doi:10.1145/3180155.3180238: "2024-06-01T15:10:00+00:00"
```

Papers already in this log are skipped on subsequent snowballing runs.

---

## Storage Format

### `project.yml`
```yaml
name: My Literature Review
description: null
researchers:
  - id: alice
    name: Alice Smith
    email: alice@example.com
  - id: bob
    name: Bob Jones
criteria:
  - id: inc1
    kind: include
    description: Empirical study on the topic
  - id: exc1
    kind: exclude
    description: Not peer-reviewed
```

### `sets/NN-kind/set.yml`
```yaml
id: 01-backward
kind: backward
iteration: 1
works:
  - wohlin2014snowballingsystematic
  - kitchenham2007guidelines
```

Sets list only the `bib_key`s of their papers; full BibTeX data lives in `works/<bib_key>.bib` and is shared across all sets that reference the same paper.

### `sets/NN-kind/decisions_<researcher_id>.yml`
```yaml
decisions:
  - work_id: doi:10.1145/3180155.3180238
    researcher_id: alice
    verdict: accept
    criterion_id: inc1
    note: Directly relevant
    decided_at: "2024-06-01T10:00:00+00:00"
resolutions: []
```
