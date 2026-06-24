# Snowballing

Snowballing grows a Systematic Literature Review from a **seed** set of papers by
following citation links. Snower derives each paper's set membership from the
citation graph — you declare the seeds and the edges, and Snower places every
paper into a round-numbered set automatically.

## Directions

Each paper has two kinds of incident edges:

- **Backward** — the paper's **references** (the works it cites).
- **Forward** — the paper's **citations** (the works that cite it).

A single directed edge "A cites B" may be stored on either side — on
`A.references` and/or on `B.citations`. Both are honoured, so only one side needs
to be written; the missing side is recovered at runtime by scanning the opposite
field (the runtime reverse index).

## Placement rules

1. **Seeds** are placed in the `start` set, round **0**.
2. Reaching paper X from an *included* parent P:
   - via a **reference** edge (P cites X) → a **backward** set;
   - via a **citation** edge (X cites P) → a **forward** set.

   In both cases `round(X) = round(P) + 1`.
3. **Minimum round wins.** X's round is the minimum over all included parents that
   reach it, and X sits in that single lowest-round set. (A@1 cites X while B@4
   references X ⇒ X is `backward-2`.)
4. **Exclude is the only removal.** An excluded paper keeps its own set/round but
   does **not** propagate: its dependents re-derive through other included parents,
   or become orphans. `include` re-enables propagation.
5. A paper with no included path back to a seed lands in the **orphan** set,
   round **-1** (reported as `orphan--1`).
6. **One set per paper.** On a same-round backward/forward tie, **backward wins**.
7. Placements stay live after every mutation.

## Incremental placement

There is no global recompute on the hot path. Each mutator adjusts placement in
place:

- `add_reference` / `add_citation` / `include` only ever *lower* a round, so they
  **relax and cascade**: a placed, included paper offers each backward neighbour
  `(backward, round + 1)` and each forward neighbour `(forward, round + 1)`;
  whenever a neighbour improves it is re-processed, so the change ripples outward
  and stops as soon as nothing improves.
- `exclude` re-derives placement by snowballing from the seeds again. Exclusion is
  the subtle case (a paper may have several equal-length paths), and it is far
  rarer than edge-adds, so a full re-derivation is used for correctness and
  simplicity.

`Project.load` performs the same one-time snowball from the seeds to rebuild
placement from the stored graph; the `sets/` files on disk are only a snapshot.

## Example

```python
from snower import Project, Paper

project = Project(name="my-slr", path="projects/my-slr")
project.add_seed(Paper(bib_id="seed2020review", title="A Review", year=2020))

project.add_paper(Paper(bib_id="smith2015method", title="A Method", year=2015))
project.add_reference("seed2020review", "smith2015method")   # seed cites smith
project.set_of("smith2015method")        # -> "backward-1"

project.exclude("smith2015method")       # screened out; stops propagating
project.include("smith2015method")       # bring it back
```
