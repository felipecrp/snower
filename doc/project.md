# Project

A `Project` is a named workspace for one Systematic Literature Review snowballing run. It owns a canonical map of papers and any number of named paper sets that reference those papers by `bib_id`.

## Concepts

**Paper map** — `Project.papers` is a `dict[bib_id, Paper]`. Every paper is stored exactly once here regardless of how many sets it belongs to.

**Paper sets** — `Project.paper_sets` is a `dict[name, PaperSet]`. Each `PaperSet` belongs to a snowballing `round` (0 = seed, 1 = round 1, …) and holds a `set[str]` of `bib_id` references into the paper map. Each paper belongs to **at most one set**; use `move_to_set` to relocate a paper between sets.

## On-disk layout

```
<project path>/
  project.yml          # name + paper_sets (each: name, round, paper_ids)
  papers/              # one YAML file per paper
    kitchenham2009systematic.yml
    beethoven1827classical.yml
```

`path` is the project's identity/location and is **not** written to `project.yml`. Paper contents live only under `papers/`; `project.yml` references them by `bib_id`.

## Usage

```python
from snower import Project, parse_bibtex

papers = parse_bibtex(open("refs.bib").read())

# create project
project = Project(name="my-slr", path="projects/my-slr")

# create a paper set for the seed round
project.add_set("seed", round=0)

# add papers to the set (also registers them in the paper map)
for paper in papers:
    project.add_to_set("seed", paper)

# resolve set members back to Paper objects
seed_papers = project.papers_in("seed")

# persist to disk
project.save()

# reload later
project = Project.load("projects/my-slr")
```

## API

### `PaperSet`

| Member | Description |
|---|---|
| `name: str` | Set name (e.g. `"seed"`, `"round1-backward"`) |
| `round: int` | Snowballing round number |
| `paper_ids: set[str]` | `bib_id` references into the project paper map |
| `add(bib_id)` | Add a `bib_id`; duplicates are silently ignored |
| `remove(bib_id)` | Remove a `bib_id`; no-op if not present |

### `Project`

| Member | Description |
|---|---|
| `name: str` | Human-readable project name |
| `path: Path` | Directory where the project is stored |
| `papers: dict[str, Paper]` | Canonical paper map keyed by `bib_id` |
| `paper_sets: dict[str, PaperSet]` | Named sets keyed by set name |
| `add_paper(paper)` | Register a paper; raises `ValueError` if `bib_id` is missing |
| `add_set(name, round)` | Create a set; returns existing set if name already exists |
| `set_of(bib_id)` | Return the set name containing this paper, or `None` |
| `add_to_set(set_name, paper)` | `add_paper` + append to set; raises `KeyError` if set absent, `ValueError` if paper already belongs to a different set |
| `move_to_set(set_name, paper)` | Move paper into set, removing it from any current set; raises `KeyError` if set absent |
| `papers_in(set_name)` | Resolve set `paper_ids` to `Paper` objects |
| `save()` | Write `project.yml` and `papers/` to disk; returns the project path |
| `Project.load(path)` | Class method — load a project from disk |
