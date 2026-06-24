# Snowballing

Snowballing grows a Systematic Literature Review from a **seed** set of papers by
following citation links. Snower derives each paper's set membership from the
citation graph — you declare the seeds and the edges, and Snower places every
paper into a round-numbered set automatically.

## Directions

Each paper has two independent directed-neighbour sets:

- **Backward** — `paper.references`: the works this paper cites.
- **Forward** — `paper.citations`: the works that cite this paper.

The two sets are **independent**: storing an edge on one side does not imply the
other. `add_reference("A", "B")` records `B` in `A.references`; `B.citations` is
not touched and `A` will not appear in `citations_of("B")`. To record the same
logical edge from the other direction, call `add_citation("B", "A")` explicitly.

## Placement rules

1. **Seeds** are placed in the `start` set, round **0**.
2. Reaching paper X from an *included* parent P:
   - via a **reference** edge (`X ∈ P.references`, P cites X) → a **backward** set;
   - via a **citation** edge (`X ∈ P.citations`, X cites P) → a **forward** set.

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
7. Placements are always up-to-date after every mutation.

## BFS derivation

After every mutation, `Project._derive()` rebuilds `_placement` in one layered
BFS from the seeds. There is no incremental update or reverse-index scan.

```
placement = {seed: ("start", 0) for seed in seeds if seed in papers}
frontier = list(placement); round = 0

while frontier:
    round += 1
    next_frontier = []
    for direction, attr in [("backward", "references"), ("forward", "citations")]:
        for member in frontier:
            if not papers[member].included:   # excluded: keeps its set, does not propagate
                continue
            for nb in getattr(papers[member], attr):
                if nb not in papers or nb in placement:   # unknown or already placed → skip
                    continue
                placement[nb] = (direction, round)
                next_frontier.append(nb)
    frontier = next_frontier
```

**Why BFS gives the right answers:**

- Each paper is placed the first time it is reached, which is also the shortest
  path from any seed (rule 3: minimum round).
- Within a round, the backward pass runs across the entire frontier before the
  forward pass begins. A paper placed by the backward pass is already in
  `placement` when the forward pass encounters it, so the forward candidate is
  skipped — backward wins the tie (rule 6).
- An excluded member is skipped in the inner loop, so its neighbours are not
  offered a placement through it (rule 4); the excluded member itself was already
  placed in an earlier round (or the same round via another path) and keeps that
  placement.
- Papers never reached are absent from `placement` and reported as orphan (rule 5).

`Project.load` calls `_derive()` after reconstructing the graph from disk; the
`sets/` files are only a materialised snapshot and are never used as the source of
truth.

## Example

```python
from snower import Project, Paper

project = Project(name="my-slr", path="projects/my-slr")
project.add_seed(Paper(bib_id="seed2020review", title="A Review", year=2020))

project.add_paper(Paper(bib_id="smith2015method", title="A Method", year=2015))
project.add_reference("seed2020review", "smith2015method")   # seed cites smith
project.set_of("smith2015method")        # -> "backward-1"

# Directions are independent: the reference above does NOT make seed appear
# in citations_of("smith2015method") — that would require add_citation explicitly.
project.citations_of("smith2015method")  # -> []

project.exclude("smith2015method")       # screened out; stops propagating
project.include("smith2015method")       # bring it back
```
