# Bidding — Researcher Assignment Algorithm

Bidding automates the assignment of papers to researchers for screening according to their availability. Each researcher specifies a percentage of papers they can screen; the algorithm ensures fair distribution with minimal overlap.

## Overview

The bidding system distributes papers across a research team based on **assignment percentages** (0–100 per researcher). If the sum of percentages exceeds 100%, overlap emerges naturally—papers are assigned to multiple researchers for cross-validation. If it's below 100%, some papers may not be assigned to anyone.

**Key properties:**
- Preserves existing manual assignments (you can bid on papers, then run the algorithm)
- Deterministic with a fixed RNG seed
- Prefers unassigned papers first to minimize overlap
- Works per set (each iteration gets its own assignment run)

## Algorithm

The `assign_bidding()` function in `snow/domain/bidding.py` implements the core logic:

```python
def assign_bidding(
    work_ids: list[str],
    researchers: list[Researcher],
    existing: dict[str, set[str]],  # researcher_email -> {work_ids}
    rng: random.Random,
) -> dict[str, set[str]]:
```

### Steps

1. **Initialize targets**: For each researcher, compute the target count:
   ```
   target = round(N * assignment_percentage / 100)
   ```
   where N is the total number of papers in the set.

2. **Sort by remaining gap**: Researchers are processed in order of the largest remaining deficit (target - currently_assigned). This ensures researchers who have fewer papers get filled first.

3. **Assign per researcher**: For each researcher (in order), assign enough papers to reach their target:
   - Build a pool of available papers (not already assigned to this researcher)
   - **Prefer unassigned papers**: Papers with zero current assignments come first in the pool
   - **Then papers with overlap**: Papers already assigned to 1+ other researchers
   - Shuffle both pools (random but seeded)
   - Take the first `need` papers from the combined pool

4. **Return full assignment**: A dict mapping researcher email → set of work IDs.

### Example: 3 Researchers, 10 Papers

```
Researchers:
  alice@example.com: 60%
  bob@example.com:   50%
  charlie@example.com: 40%

Papers: [w0, w1, w2, w3, w4, w5, w6, w7, w8, w9]

Targets:
  alice:   round(10 * 60 / 100) = 6
  bob:     round(10 * 50 / 100) = 5
  charlie: round(10 * 40 / 100) = 4

Processing order (by largest gap):
  1. alice:   0 → need 6
  2. bob:     0 → need 5
  3. charlie: 0 → need 4

Result (deterministic with seed=42):
  alice:   {w0, w2, w4, w6, w8, w9}
  bob:     {w1, w3, w5, w7, w8}
  charlie: {w0, w1, w2, w3}

Overlap: 4 papers (w0, w1, w2, w3, w8) assigned to 2+ researchers
Overlap %: 40%
```

### Overlap & Natural Minimum

When assignment percentages sum to more than 100%, overlap is **inevitable and desired** for quality assurance. The algorithm minimizes overlap by preferring unassigned papers first.

**Example:**
- alice: 60%, bob: 60% (sum = 120%, 10 papers)
- Natural minimum overlap: 120% − 100% = 20% of 10 = 2 papers

## Preservation of Existing Assignments

The algorithm respects manual assignments (bids). If you bid on a paper, it counts toward your target and remains assigned after running the algorithm.

**Example:**
```
Existing: alice has already bid on {w0, w1, w2}
Target:   alice should have 6 papers
New need: 6 − 3 = 3 more papers

After run: alice has {w0, w1, w2} + 3 randomly chosen unassigned papers
```

If you have **more papers than your target** (e.g., bidded on 8, target is 6), all 8 are preserved.

## API Endpoints

### Get Biddings for a Set
```
GET /api/sets/{set_id}/bidding
```
Returns a list of `Bidding` objects (researcher_id, work_ids).

### Manually Bid on a Paper
```
PUT /api/sets/{set_id}/bidding/{work_id}
```
Adds the active researcher to the bidding list for this paper. Requires the `X-Researcher-Id` header.

### Remove a Bid
```
DELETE /api/sets/{set_id}/bidding/{work_id}
```
Removes the active researcher from the bidding list.

### Run the Bidding Algorithm
```
POST /api/bidding/run
```
Runs the full assignment algorithm across all sets. Returns a summary for each set:
```json
{
  "set_id": "00-start",
  "total_works": 50,
  "per_researcher": {
    "alice@example.com": 30,
    "bob@example.com": 25,
    "charlie@example.com": 20
  },
  "overlap_pct": 15.0
}
```

## Data Structures

### Bidding Model
```python
class Bidding(BaseModel):
    researcher_id: str      # Researcher email
    work_ids: list[str]     # Sorted BibTeX keys
```

### Storage
Biddings are stored in `<project>/sets/{set_id}/biddings.yml`:
```yaml
- researcher_id: alice@example.com
  work_ids:
    - smith2018machine
    - jones2019deep
    - clark2020learning

- researcher_id: bob@example.com
  work_ids:
    - smith2018machine
    - brown2019neural
```

## UI Integration

**Manual Bidding:**
- In the paper list, each researcher sees a **circle with + or −**
- Click **+** to bid on a paper (add yourself to the assignment list)
- Click **−** to remove your bid
- Button turns blue when bidded; gray when not

**Automatic Assignment:**
- Click the **Bidding** button in the sidebar to run the algorithm
- The system assigns papers according to each researcher's percentage
- Existing bids are preserved and count toward the target
- UI updates with the new assignments

## Workflow Example

1. **Setup researchers** in Project settings:
   - alice: 60% (can screen 60 papers per set)
   - bob: 50% (can screen 50 papers per set)

2. **Manual review** (optional):
   - Researchers browse papers and bid on ones they prefer
   - Alice bids on 5 papers she's interested in

3. **Run bidding**:
   - Click the Bidding button
   - System calculates: alice needs 6 total, already has 5 → adds 1
   - System calculates: bob needs 5 total, has 0 → adds 5
   - Papers assigned with alice's 5 bids preserved

4. **Screen papers**:
   - Each researcher screens their assigned papers using the decision dropdown
   - Papers with multiple assignments benefit from cross-validation

## Test Suite

See `tests/domain/test_bidding.py` for comprehensive examples:

- Empty works → empty assignment
- Respects existing assignments
- Meets percentage targets
- Handles overlap correctly
- Deterministic with seeded RNG
- Preserves bids beyond target count
- Does not exceed available papers (when sum > 100%)

## Implementation Files

- `snow/domain/bidding.py` — Core algorithm
- `snow/api/routers/bidding.py` — REST endpoints
- `tests/domain/test_bidding.py` — Unit tests
- `tests/api/test_bidding_router.py` — Integration tests
