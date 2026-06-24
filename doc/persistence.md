# Persistence

`PaperRepository` stores each paper as a YAML file named `{bib_id}.yml` inside a directory.

## File layout

```
papers/
  kitchenham2009systematic.yml
  beethoven1827classical.yml
```

## Completeness rule

A paper can only be saved when all four fields are present: `bib_id`, `authors` (non-empty), `title`, and `year`. Calling `save()` on an incomplete paper raises `ValueError` listing the missing fields.

## Usage

```python
from snower import PaperRepository, parse_bibtex

papers = parse_bibtex(open("refs.bib").read())
repo = PaperRepository("papers/")

# save
for paper in papers:
    repo.save(paper)

# load one
paper = repo.load("kitchenham2009systematic")

# load all
all_papers = repo.load_all()
```
