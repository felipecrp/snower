# Consensus and Perspective

## What is consensus?

In multi-researcher projects each researcher records an independent decision for every paper. Consensus is the aggregated verdict:

- **Accept consensus**: accept votes > reject votes
- **Reject consensus**: reject votes > accept votes
- **Undecided** (tie or no votes): accept votes = reject votes, or no researcher has voted yet

The sidebar counter `X/Y` always shows consensus-accepted / total, regardless of the active perspective.

## Perspectives

The Snowballing panel offers two perspectives that change how papers are classified and filtered. The toggle appears in the sidebar **below the Orphan set**, and is only shown when the project has more than one researcher.

### Researcher (default)

Classification is based on the **active researcher's own decision**:

| Classification | Condition |
|---|---|
| Accepted | Active researcher voted accept |
| Rejected | Active researcher voted reject |
| Undecided | Active researcher has not voted |

Use this perspective during daily triage — it reflects your personal worklist.

### Majority

Classification is based on the **group's consensus**:

| Classification | Condition |
|---|---|
| Accepted | Accept votes > reject votes |
| Rejected | Reject votes > accept votes |
| Undecided | Tie or no votes |

In Majority mode each paper card shows a one-line vote summary above the action controls, e.g.:

```
Alice and Bob accepted · Carol rejected
```

Researchers who have not voted on that paper are omitted. The criterion dropdown and all other edit controls remain fully functional — the active researcher can still cast or change their own decision while in Majority mode.

## Verdict badge

Every paper card always shows a verdict badge reflecting the active perspective:

| Badge | Researcher mode | Majority mode |
|---|---|---|
| **accepted** (green) | Active researcher voted accept | Accept votes > reject votes |
| **rejected** (red) | Active researcher voted reject | Reject votes > accept votes |
| **undecided** (grey) | Active researcher has not voted | Tie or no votes |

## Filter chips

The filter bar shows a compact chip row:

```
show  [✓ 25 accepted]  [✓ 0 rejected]  [✓ 10 undecided]  |  [  30 assigned to me]   42 shown
```

- **accepted / rejected / undecided** — OR visibility toggles. Uncheck one to hide those papers. Counts reflect the active perspective.
- **assigned to me** — AND narrowing filter. When checked, the list is further restricted to papers the active researcher has bid on (see [bidding.md](bidding.md)).
- **N shown** — live count of visible papers after all chip filters are applied.

Combined semantics:

```
visible = (accepted? ∪ rejected? ∪ undecided?) ∩ (assigned-to-me? if checked)
```

## Persistence

Both the active perspective and each chip's state are saved in `localStorage` and restored on page reload.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `f + a` | Toggle accepted chip |
| `f + r` | Toggle rejected chip |
| `f + u` | Toggle undecided chip |
| `f + f` | Toggle perspective (Researcher ↔ Majority) |

See [shortcuts.md](shortcuts.md) for the full shortcut reference.
