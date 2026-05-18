"""Bidding assignment algorithm.

Distributes works across researchers according to their assignment_percentage,
preserving existing assignments.  Overlap emerges naturally when the sum of
percentages exceeds 100.
"""

from __future__ import annotations

import random

from snow.domain.models import Researcher


def assign_bidding(
    work_ids: list[str],
    researchers: list[Researcher],
    existing: dict[str, set[str]],
    rng: random.Random,
) -> dict[str, set[str]]:
    """Return researcher_id -> set of work_ids for the full assignment.

    Preserves all entries in `existing`.  Each researcher gets approximately
    round(N * assignment_percentage / 100) papers, chosen randomly from the
    papers not yet assigned to them.  Researchers with the largest remaining
    gap are filled first.  Unassigned papers are preferred to keep overlap at
    the natural minimum (sum_of_percentages - 100%).
    """
    n = len(work_ids)
    result: dict[str, set[str]] = {r.email: set(existing.get(r.email, set())) for r in researchers}

    if n == 0 or not researchers:
        return result

    targets: dict[str, int] = {r.email: round(n * r.assignment_percentage / 100) for r in researchers}

    ordered = sorted(researchers, key=lambda r: targets[r.email] - len(result[r.email]), reverse=True)

    for r in ordered:
        need = targets[r.email] - len(result[r.email])
        if need <= 0:
            continue

        available = [w for w in work_ids if w not in result[r.email]]
        if not available:
            continue

        counts = _assignment_counts(work_ids, result)
        # Prefer unassigned papers first to keep overlap at the natural minimum.
        no_coverage = [w for w in available if counts[w] == 0]
        has_coverage = [w for w in available if counts[w] > 0]
        rng.shuffle(no_coverage)
        rng.shuffle(has_coverage)
        pool = no_coverage + has_coverage
        result[r.email].update(pool[:need])

    return result


def _assignment_counts(work_ids: list[str], result: dict[str, set[str]]) -> dict[str, int]:
    counts = {w: 0 for w in work_ids}
    for assigned in result.values():
        for w in assigned:
            if w in counts:
                counts[w] += 1
    return counts
