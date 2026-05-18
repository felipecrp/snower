import random

import pytest

from snow.domain.bidding import assign_bidding
from snow.domain.models import Researcher


def _r(email: str, pct: int) -> Researcher:
    return Researcher(email=email, name=email, assignment_percentage=pct)


WORKS = [f"w{i}" for i in range(10)]


class Describe_assign_bidding:
    def it_returns_empty_for_no_works(self):
        r = _r("a@x.com", 100)
        result = assign_bidding([], [r], {}, random.Random(0))
        assert result == {"a@x.com": set()}

    def it_returns_empty_for_no_researchers(self):
        result = assign_bidding(WORKS, [], {}, random.Random(0))
        assert result == {}

    def it_meets_per_researcher_percentage(self):
        researchers = [_r("a@x.com", 60), _r("b@x.com", 50)]
        result = assign_bidding(WORKS, researchers, {}, random.Random(42))
        assert len(result["a@x.com"]) == 6
        assert len(result["b@x.com"]) == 5

    def it_respects_existing_assignments(self):
        existing = {"a@x.com": {"w0", "w1", "w2"}}
        researchers = [_r("a@x.com", 60)]
        result = assign_bidding(WORKS, researchers, existing, random.Random(0))
        assert {"w0", "w1", "w2"}.issubset(result["a@x.com"])
        assert len(result["a@x.com"]) == 6

    def it_does_not_exceed_available_works(self):
        researchers = [_r("a@x.com", 100), _r("b@x.com", 100)]
        result = assign_bidding(WORKS, researchers, {}, random.Random(0))
        assert len(result["a@x.com"]) == 10
        assert len(result["b@x.com"]) == 10

    def it_produces_natural_overlap_when_sum_exceeds_100(self):
        researchers = [_r("a@x.com", 60), _r("b@x.com", 60)]
        result = assign_bidding(WORKS, researchers, {}, random.Random(1))
        overlap = result["a@x.com"] & result["b@x.com"]
        assert len(overlap) == 2  # 120% - 100% = 20% of 10 = 2

    def it_is_deterministic_with_seeded_rng(self):
        researchers = [_r("a@x.com", 60), _r("b@x.com", 50)]
        r1 = assign_bidding(WORKS, researchers, {}, random.Random(99))
        r2 = assign_bidding(WORKS, researchers, {}, random.Random(99))
        assert r1 == r2

    def it_preserves_existing_beyond_target(self):
        existing = {"a@x.com": set(WORKS)}  # all 10, but target is 6
        researchers = [_r("a@x.com", 60)]
        result = assign_bidding(WORKS, researchers, existing, random.Random(0))
        assert result["a@x.com"] == set(WORKS)
