# Review: Criteria, Phases, Researchers & Assessments

Snower supports structured screening via three project-level reference lists and a per-paper, per-researcher assessment record.

## Reference lists

**Criteria** (`/criteria`) — inclusion or exclusion criteria used to justify a screening decision. Each criterion has an `id`, `name`, and `type` (`inclusion` | `exclusion`).

**Phases** (`/phases`) — reading phases in the review protocol (e.g., title screening, abstract screening, full-text reading). Each phase has an `id` and `name`.

**Researchers** (`/researchers`) — people participating in the review. Each researcher has an `email` (unique identifier) and `name`.

These lists are managed via CRUD endpoints and persisted in `project.yml`.

## Assessments

A paper collects assessments from multiple researchers. Each assessment records which criterion and phase a researcher chose when screening a paper. The `included` meaning is **derived** from the criterion's type — there is no stored boolean.

```
POST /papers/{bib_id}  ← sends criterion_id, phase_id, researcher_email
```

The same researcher re-assessing the same paper overwrites their previous entry (latest opinion wins). A second researcher adds a second entry.

### Derived `included`

```python
assessment.included  # True if criterion.type == "inclusion", False if "exclusion"
```

### Final decision

Assessments are *opinions*. Each time a review is recorded, the project's **decision strategy** recomputes the paper's `decision` (`included` / `excluded` / `undecided`) from all its assessments. Only a `decision == excluded` paper halts snowball propagation; `undecided` papers propagate normally. See [doc/decision.md](decision.md) for the available strategies.

## On-disk layout

```
project.yml        # name, seeds, criteria, phases, researchers
papers/            # one file per paper
sets/              # derived snapshot
review/            # one file per researcher
  a@b.com.yml      #   { bib_id: { criterion: {...}, phase: {...} } }
```

Assessments are split out of `project.yml` into `review/` so that concurrent edits by different researchers touch different files, producing merge-friendly diffs.
