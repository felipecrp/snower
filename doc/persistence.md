# Persistence

A project persists as three parallel YAML stores plus a small metadata file:

- `PaperRepository` stores each paper as `{bib_id}.yml` (the graph: `references`,
  `citations`, and bibliographic fields). `decision` is not persisted — it is
  recomputed from reviews on every load and after every update.
- `SetRepository` stores each derived `PaperSet` as `{name}-{round}.yml`.
- `ReviewRepository` stores assessments as `review/{email}.yml`, one file per researcher.
- `project.yml` holds `name`, `seeds`, `criteria`, `phases`, `researchers`, and `decision_strategy`.

## File layout

```
project.yml                        # name, seeds, criteria, phases, researchers, decision_strategy
papers/
  kitchenham2009systematic.yml     # references / citations / bibliographic fields
  beethoven1827classical.yml
sets/
  start-0.yml                      # name, round, paper_ids
  backward-1.yml
  forward-2.yml
  orphan--1.yml
review/
  a@b.com.yml                      # { bib_id: { criterion: {...}, phase: {...} } }
  b@b.com.yml
```

## Completeness rule

A paper can only be saved when all four fields are present: `bib_id`, `authors`
(non-empty), `title`, and `year`. Calling `save()` on an incomplete paper raises
`ValueError` listing the missing fields. `SetRepository` has no completeness rule.

## Sets are a snapshot, not the source of truth

The graph (papers + seeds) is authoritative. The `sets/` files are a materialised
snapshot of derived placement, rewritten in full on every `Project.save()`:
`SetRepository.save_all` **clears the directory first**, so a set that became
empty leaves no stale file behind. `Project.load` ignores the snapshot and
re-derives placement by snowballing from the seeds, so the files can never drift.

## ReviewRepository

`ReviewRepository` mirrors `SetRepository` (clear-then-write):

- `save_all(assessments)` — clears `*.yml` from the directory, then writes one `{email}.yml` per researcher. Researchers with no assessments are skipped. Each file's `{bib_id: Assessment}` mapping is written sorted by bib_id for merge-friendly diffs.
- `load_all()` — reads each `*.yml`; the file stem is the researcher email; the contents become `{bib_id: Assessment}`.

`assessments` is never stored in `project.yml`; it lives entirely in `review/`. `Project.save()` calls both `SetRepository.save_all` and `ReviewRepository.save_all`.

## Usage

```python
from snower import PaperRepository, SetRepository, parse_bibtex

papers = parse_bibtex(open("refs.bib").read())
repo = PaperRepository("papers/")

for paper in papers:           # save
    repo.save(paper)
paper = repo.load("kitchenham2009systematic")   # load one
all_papers = repo.load_all()                     # load all

# sets are usually written via Project.save(), but the repository is standalone:
set_repo = SetRepository("sets/")
set_repo.save_all(my_paper_sets)   # clears the dir, then writes each set
loaded_sets = set_repo.load_all()
```
