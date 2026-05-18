# Snow — Overview

Snow is a **local-first** tool for conducting systematic literature reviews using the snowballing method (Wohlin, 2014). It is designed for researchers who need to manage iterative backward/forward snowballing across multiple sets, potentially with more than one reviewer, while keeping all data in plain text files that can be versioned with git.

## Why Snow Exists

Existing tools (Rayyan, Covidence, etc.) are SaaS products with no native iterative snowballing support. Snow fills that gap with three core properties:

- **Local and offline.** The server runs on `127.0.0.1`. No data leaves the machine.
- **Git-friendly storage.** All data is YAML and BibTeX. Every decision and paper is diffable, branchable, and mergeable.
- **Snowballing-first.** The data model is built around iterations: start → backward-1/forward-1 → backward-2/forward-2 → …

## The Snowballing Process

Wohlin's method in Snow works like this:

1. Import an initial set of seed papers as the **start set** (iteration 0).
2. Researchers triage each paper: accept or reject using inclusion/exclusion criteria.
3. Trigger **Backward snowballing**: fetch references of accepted papers → creates a new set at iteration 1.
4. Trigger **Forward snowballing**: fetch citations of accepted papers → creates a new set at iteration 1.
5. Triage the new sets and repeat. Papers from iteration N always feed into iteration N+1.
6. Check the **Results** view at any time to see which papers have majority consensus.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn |
| Domain / validation | Pydantic v2 |
| BibTeX parsing | bibtexparser 1.4.4 |
| YAML I/O | ruamel.yaml (block style, preserves comments) |
| Scholar provider | scholarly (Google Scholar scraping) |
| Frontend | Angular 21, standalone components, signals |
| Desktop wrapper | Electron (loads `http://localhost:4200` in dev) |
| CLI | Typer |
| Tests | pytest + pytest-pyspec |

## Quick Start

```bash
# Create and enter a project
snow init my-review
cd my-review
git init && git add . && git commit -m "init"

# Import seed papers
snow import-bib ~/exports/scopus.bib

# Start the API server (in one terminal)
snow serve

# Start the Angular dev server (in another terminal)
cd ui && npm run start

# Or use Electron dev mode (opens a native window)
cd ui && npm run electron:dev
```

## Project Repository Layout

```
<project>/
  project.yml          # Project config: name, researchers, criteria, providers
  keys.yml             # Global BibTeX-key → work_id registry
  snowballing.yml      # Timestamps of when each paper was snowballed (per direction)
  relations/           # Citation graph, one YAML file per paper
  sets/
    00-start/
      set.yml          # iteration, kind, parent_set_id
      articles.bib     # Papers in this set (source of truth for metadata)
      decisions.yml    # Accept/reject decisions per researcher
    01-backward/
      ...
    01-forward/
      ...
```
