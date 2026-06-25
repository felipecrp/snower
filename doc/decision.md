# Decision Strategies

## Overview

Every paper in a Snower project has a three-state **decision**:

| Value | Meaning |
|-------|---------|
| `included` | The paper passes screening |
| `excluded` | The paper fails screening |
| `undecided` | No consensus yet (default for new papers) |

The decision is a pure function of a paper's assessments and the project's selected **decision strategy**. It is recomputed automatically each time a review is recorded and on every project load.

## How decisions feed derivation

Snowball placement propagates through a paper unless its decision is `excluded`. Papers in the `included` or `undecided` state both propagate, so snowballing works correctly before any screening has taken place.

## Strategies

Both strategies ignore researchers who have not yet submitted an assessment — only present reviews count.

### Majority (`majority`, default)

Most votes win across the reviews that exist:

- More inclusions than exclusions → `included`
- More exclusions than inclusions → `excluded`
- Tie (including no reviews) → `undecided`

### Consensus (`consensus`)

All present votes must be the same:

- All reviews agree on inclusion → `included`
- All reviews agree on exclusion → `excluded`
- Any disagreement, or no reviews → `undecided`

## Switching strategies

The project's strategy is stored in `project.yml` as `decision_strategy`. Changing it via `PATCH /` (or `Project.set_decision_strategy()`) recomputes every paper's decision immediately and re-derives snowball placement.
