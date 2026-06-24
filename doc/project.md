# Project

A `Project` is a named workspace for one Systematic Literature Review snowballing
run. It owns a canonical map of papers — which double as the nodes of a citation
graph — plus the set of **seed** papers. Every paper's set membership (a direction
and a round) is **derived** from the graph rather than assigned by hand. See
[snowballing.md](snowballing.md) for the placement rules and algorithm.

## Concepts

**Paper map** — `Project.papers` is a `dict[bib_id, Paper]`. Every paper is stored
exactly once. Each `Paper` carries its own graph edges (`references`, `citations`)
and a screening flag (`included`).

**Seeds** — `Project.seeds` is a `set[bib_id]`. Seeds anchor the review at round 0
(the `start` set). Add one with `add_seed`.

**Derived sets** — a paper's set is computed from the graph, named
`"{direction}-{round}"` (e.g. `start-0`, `backward-1`, `forward-2`,
`orphan--1`). Query it with `set_of`; sets are not stored, they are projected on
demand by `papers_in` and persistence. A `PaperSet` (`name`, `round`,
`paper_ids`) is that projection — materialised for the public API and for the
`sets/` files, never the source of truth.

## On-disk layout

```
<project path>/
  project.yml               # name + seeds (no paper_sets)
  papers/                   # one YAML file per paper (incl. references/citations/included)
    seed2020review.yml
    smith2015method.yml
  sets/                     # materialised snapshot of derived placement
    start-0.yml
    backward-1.yml
    orphan--1.yml
```

`path` is the project's identity/location and is **not** written to `project.yml`.
The `sets/` files are a snapshot written on `save()`; placement is always
re-derived from the graph on `load()`, so the snapshot can never drift. See
[persistence.md](persistence.md).

## Usage

```python
from snower import Project, Paper

project = Project(name="my-slr", path="projects/my-slr")

# anchor the review with a seed (placed at start-0)
project.add_seed(Paper(bib_id="seed2020review", title="A Review", year=2020))

# register another paper and record a citation edge
project.add_paper(Paper(bib_id="smith2015method", title="A Method", year=2015))
project.add_reference("seed2020review", "smith2015method")  # seed cites smith

project.set_of("smith2015method")        # -> "backward-1"
project.papers_in("backward-1")          # -> [Paper(bib_id="smith2015method", ...)]

# screening
project.exclude("smith2015method")       # keeps its set, stops propagating
project.include("smith2015method")       # re-enable propagation

project.save()
project = Project.load("projects/my-slr")
```

## API

### `Project`

| Member | Description |
|---|---|
| `name: str` | Human-readable project name |
| `path: Path` | Directory where the project is stored |
| `papers: dict[str, Paper]` | Canonical paper map keyed by `bib_id` |
| `seeds: set[str]` | `bib_id`s anchoring the review at round 0 |
| `add_paper(paper)` | Register a paper (enters as an orphan); raises `ValueError` if `bib_id` is missing |
| `add_seed(paper)` | Register a paper as a seed, place it at `start-0`, snowball outward |
| `add_reference(citing_id, cited_id)` | Record `citing` cites `cited` and re-derive; `KeyError` if unknown, `ValueError` on self-citation |
| `add_citation(cited_id, citing_id)` | Same directed edge, recorded on the citations side |
| `include(bib_id)` | Mark included and re-enable propagation |
| `exclude(bib_id)` | Mark excluded; keeps its set but stops propagating, re-derives dependents |
| `set_of(bib_id)` | Derived set name `"{direction}-{round}"`, or `"orphan--1"` |
| `papers_in(set_name)` | Resolve a set's members to `Paper` objects |
| `references_of(bib_id)` | `Paper` objects this paper cites (full backward neighbours) |
| `citations_of(bib_id)` | `Paper` objects that cite this paper (full forward neighbours) |
| `save()` | Write `project.yml`, `papers/`, and `sets/`; returns the project path |
| `Project.load(path)` | Class method — load papers + seeds, re-derive placement |

### `PaperSet`

| Member | Description |
|---|---|
| `name: str` | Direction (`start` / `backward` / `forward` / `orphan`) |
| `round: int` | Snowballing round number |
| `paper_ids: set[str]` | `bib_id` references into the project paper map |
| `add(bib_id)` / `remove(bib_id)` | Add / remove a `bib_id` |
