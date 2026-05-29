# Snow — Testing Guide

## Running tests

```bash
# Full suite (228 tests)
uv run pytest

# One layer only
uv run pytest tests/domain/
uv run pytest tests/storage/
uv run pytest tests/api/
uv run pytest tests/e2e/

# One file
uv run pytest tests/e2e/test_snowballing_workflow.py -v

# One test
uv run pytest tests/e2e/test_triage_workflow.py::DescribeTriageWorkflow::it_records_independent_decisions_per_researcher -v
```

## Test layout

```
tests/
├── domain/       # Pure logic — no I/O, no HTTP
├── storage/      # ProjectRepo disk I/O and serialization
├── api/          # HTTP contracts via FastAPI TestClient
├── e2e/          # Multi-step workflows through the full API stack
├── providers/    # Provider factory + OpenAlex integration
├── test_cli.py   # Typer CLI commands
└── test_user_config.py
```

The tree mirrors `snow/`: a module at `snow/storage/repo.py` has its tests in `tests/storage/test_repo.py`.

## Layer responsibilities

| Layer | Owns | Does not own |
|---|---|---|
| `tests/domain/` | Pure functions: `work_id`, `mint_bib_key`, consensus rule, fingerprints | Disk I/O, HTTP |
| `tests/storage/` | `ProjectRepo` round-trips, on-disk file layout, serialization edge cases | HTTP contracts, auth |
| `tests/api/` | HTTP status codes, auth (401/403), 404s, request/response shape | Business logic already covered in storage |
| `tests/e2e/` | Multi-endpoint workflows: triage → snowballing → orphan recalculation | Isolated unit behaviour |

## Naming conventions (`pytest-pyspec`)

Classes are named `Describe<Subject>` and methods `it_<behaviour>`:

```python
class DescribeTriageWorkflow:
    def it_records_independent_decisions_per_researcher(self, client, alice, bob):
        ...
```

`pytest-pyspec` formats these as readable sentences in the output.

## Fixtures

### `tests/api/conftest.py`
| Fixture | What it provides |
|---|---|
| `project_dir` | `tmp_path` project seeded with 2 criteria, 2 researchers (Alice, Bob), and 2 start-set works |
| `client` | `FastAPI.TestClient` bound to that project |
| `alice_headers` | `{"X-Researcher-Id": "alice@example.com"}` |

### `tests/e2e/conftest.py`
| Fixture | What it provides |
|---|---|
| `project_dir` | `tmp_path` project with 2 criteria and 2 researchers — no pre-imported papers |
| `client` | `FastAPI.TestClient` bound to that project |
| `alice` / `bob` | `X-Researcher-Id` header dicts |

Helper functions (not fixtures):

- `import_work(client, set_id, title, year)` — imports a single work with `?enrich=false` and returns its `bib_key`.
- `decide(client, set_id, bib_key, verdict, criterion_id, headers)` — wraps `PUT /api/sets/{set_id}/decisions/{bib_key}`.
- `mock_provider(references, citations)` — returns a `MagicMock` `Provider` with fixed `fetch_references` / `fetch_citations` results.

## E2E tests and provider mocking

E2E tests exercise complete workflows through the real API stack using `FastAPI.TestClient` (no browser, no network). Two techniques keep them hermetic:

1. **`?enrich=false`** on `POST /api/sets/{set_id}/import-work` — skips the OpenAlex enrichment call.
2. **`unittest.mock.patch`** on `snow.api.routers.snowballing.get_provider` — injects a `mock_provider` that returns canned `BibliographicWork` objects instead of hitting any external service.

```python
from unittest.mock import patch
from tests.e2e.conftest import mock_provider

provider = mock_provider(references=[BibliographicWork(title="Ref A", authors=("A, A",), year=2015)])
with patch("snow.api.routers.snowballing.get_provider", return_value=provider):
    r = client.post("/api/snowballing/backward")
```

## Coverage by feature area

| Feature area | Primary test file(s) |
|---|---|
| Workspace & project lifecycle | `tests/api/test_workspace.py` |
| Researcher CRUD + cascade | `tests/api/test_project.py` — `DescribeRenameResearcher`, `DescribeRemoveResearcher` |
| Criteria & phases CRUD | `tests/api/test_project.py` — `DescribeReplaceCriteria`, `DescribeReplacePhases` |
| Sets & BibTeX import | `tests/api/test_sets.py` |
| BibTeX per-paper edit | `tests/api/test_works_bibtex.py` |
| Decisions (triage) | `tests/api/test_decisions.py`, `tests/e2e/test_triage_workflow.py` |
| Snowballing lifecycle | `tests/storage/test_repo.py`, `tests/e2e/test_snowballing_workflow.py` |
| Orphan lifecycle | `tests/storage/test_repo.py`, `tests/e2e/test_orphan_lifecycle.py` |
| Bidding | `tests/domain/test_bidding.py`, `tests/api/test_bidding_router.py` |
| Identity / key minting | `tests/domain/test_identity.py` |
| Storage serialization | `tests/storage/test_bib.py`, `tests/storage/test_yml.py`, `tests/storage/test_tabular.py` |
| Provider factory | `tests/providers/test_factory.py` |
| CLI | `tests/test_cli.py` |
