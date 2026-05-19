# UI Guide

The Angular frontend is a single-page application with two screens: **Triage** and **Settings**.

## Triage Screen

The main working screen. Layout:

```
┌──────────────────────────────────────────────────────┐
│ Snow — <project name>      View as: [dropdown]  ⚙    │  ← topbar
├────────────┬─────────────────────────────────────────┤
│ Sets       │ [filter bar: sort, show selected, …]    │
│            │                                         │
│ 00-start   │  ┌────────────────────────────────────┐ │
│  2/5       │  │ Paper title                        │ │
│ 01-backward│  │ Authors · Year · Venue · DOI       │ │
│  1/3       │  │ Abstract                           │ │
│            │  │ [criterion dropdown] [badge] [note]│ │
│            │  └────────────────────────────────────┘ │
│ [Backward] │                                         │
│ [Forward]  │                                         │
└────────────┴─────────────────────────────────────────┘
```

### Researcher Dropdown

Located in the topbar. Selects the active researcher whose decisions are shown and edited.

| Option | Behaviour |
|---|---|
| `— select —` | No researcher active; cards show a placeholder message |
| `<researcher name>` | Triage mode for that researcher |

### Sets Sidebar

Lists all sets ordered by id. Each row shows:
- **Set id** (e.g. `01-backward`)
- **Set kind** (e.g. `backward`)
- **X/Y counter**: X = papers accepted by majority consensus, Y = total in the set

At the bottom of the sidebar:
- **Backward** button — triggers global backward snowballing
- **Forward** button — triggers global forward snowballing

### Filter Bar

Sticky bar above the paper list (visible only when a set is selected):

- **Sort by**: author / title / journal/conference / criterion
- **Chip row**: compact visibility toggles — `accepted`, `rejected`, `undecided` (OR filters) and `assigned to me` (AND narrowing filter). Each chip shows its count. See [consensus.md](consensus.md) for full semantics.
- **N shown**: live count of papers visible after all chip filters.

### Perspective Toggle

Located in the sidebar below the Orphan set (only shown for multi-researcher projects). Switches between **Researcher** (personal decisions) and **Majority** (group consensus) perspectives. Both perspectives keep the same triage controls — Majority mode adds a per-researcher vote summary line above the action buttons. See [consensus.md](consensus.md).

### Paper Cards

Each paper card shows:
- Header: title, authors, year, venue, DOI link
- In **Majority** perspective: a vote summary line, e.g. `Alice and Bob accepted · Carol rejected`
- **Criterion dropdown**: selecting an `include` criterion saves an `accept` decision; selecting an `exclude` criterion saves a `reject` decision; selecting `— no decision —` deletes the decision
- **Verdict badge**: always visible — shows `accepted`, `rejected`, or `undecided` based on the active perspective (see [consensus.md](consensus.md))
- **Note field**: optional justification, saved on blur

### Keyboard Shortcuts

Available whenever the criterion dialog is closed and focus is not in a text field:

| Key | Action |
|---|---|
| `j` | Move selection down |
| `k` | Move selection up |
| `a` | Open criterion dialog — accept (include criteria) |
| `r` | Open criterion dialog — reject (exclude criteria) |
| `s` | Cycle sort field |
| `t` | Cycle visibility mode (pending → selected → rejected → all) |

### Criterion Dialog

Opened by pressing `a` or `r`. A modal with:
- Fuzzy search input (auto-focused)
- Optional justification note
- List of matching criteria, highlighted with arrow keys
- `Enter` to confirm, `Escape` to cancel

The last used criterion per direction (`accept`/`reject`) is shown first in the list.

## Settings Screen

Accessed via the gear icon in the topbar (`/settings`).

Allows managing:
- **Researchers**: id, name, email. Renaming an id (via `previous_id`) propagates to all decisions.
- **Criteria**: id, kind (include/exclude), description. Renaming an id propagates to all decisions.

Removing a researcher deletes all their decisions across every set.
