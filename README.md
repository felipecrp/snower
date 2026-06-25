# Snower

Snower is a tool to assist the snowballing process in a Systematic Literature Review (SLR). The snowballing workflow starts from a seed set of papers and expands it via backward (references) and forward (citations) snowballing, with screening decisions across iterations.

A paper's `references` and `citations` edges drive **automatic round placement**: instead of assigning papers to sets by hand, you declare the seeds and the citation edges, and Snower derives each paper's set (a backward/forward direction and a round number) by snowballing from the seeds. Screening is done by **excluding** a paper, which retracts its contribution and re-derives everyone downstream. For structured screening with criteria, phases, and multiple researchers see [doc/review.md](doc/review.md). See also [doc/snowballing.md](doc/snowballing.md), [doc/project.md](doc/project.md), [doc/persistence.md](doc/persistence.md), [doc/api.md](doc/api.md), and [doc/frontend.md](doc/frontend.md).

## Running

Open two terminals from the repo root.

**Terminal 1 — backend:**

```bash
SNOWER_PROJECT_PATH=./projects/myproject uv run uvicorn snower.api.app:app --reload
```

`SNOWER_PROJECT_PATH` points to the project directory to serve (default: `./project`). The API runs at `http://localhost:8000`; interactive docs at `http://localhost:8000/docs`.

**Terminal 2 — frontend:**

```bash
cd frontend
npm start
```

The Angular dev server runs at `http://localhost:4200`.
