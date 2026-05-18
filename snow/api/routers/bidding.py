"""Bidding endpoints — paper assignment per researcher per set."""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from snow.api.state import get_active_researcher, get_repo
from snow.domain.bidding import assign_bidding
from snow.domain.models import Bidding, Researcher
from snow.storage.repo import ProjectRepo

router = APIRouter(tags=["bidding"])


class BiddingRunSummary(BaseModel):
    set_id: str
    total_works: int
    per_researcher: dict[str, int]
    overlap_pct: float


def _ensure_set_exists(repo: ProjectRepo, set_id: str) -> None:
    if set_id not in repo.list_set_ids():
        raise HTTPException(404, f"Set not found: {set_id}")


@router.get("/api/sets/{set_id}/bidding", response_model=list[Bidding])
def get_biddings(set_id: str, repo: ProjectRepo = Depends(get_repo)) -> list[Bidding]:
    _ensure_set_exists(repo, set_id)
    return repo.load_biddings(set_id)


@router.put("/api/sets/{set_id}/bidding/{work_id:path}", response_model=Bidding)
def add_bid(
    set_id: str,
    work_id: str,
    repo: ProjectRepo = Depends(get_repo),
    researcher: Researcher = Depends(get_active_researcher),
) -> Bidding:
    _ensure_set_exists(repo, set_id)
    return repo.add_work_to_bidding(set_id, researcher.email, work_id)


@router.delete("/api/sets/{set_id}/bidding/{work_id:path}", response_model=Bidding)
def remove_bid(
    set_id: str,
    work_id: str,
    repo: ProjectRepo = Depends(get_repo),
    researcher: Researcher = Depends(get_active_researcher),
) -> Bidding:
    _ensure_set_exists(repo, set_id)
    return repo.remove_work_from_bidding(set_id, researcher.email, work_id)


@router.post("/api/bidding/run", response_model=list[BiddingRunSummary])
def run_bidding(repo: ProjectRepo = Depends(get_repo)) -> list[BiddingRunSummary]:
    project = repo.load_project()
    researchers = project.researchers
    if not researchers:
        return []

    rng = random.Random()
    summaries: list[BiddingRunSummary] = []

    for set_id in repo.list_set_ids():
        s = repo.load_set(set_id)
        work_ids = [w.bib_key for w in s.works]
        if not work_ids:
            continue

        existing_biddings = repo.load_biddings(set_id)
        existing = {b.researcher_id: set(b.work_ids) for b in existing_biddings}

        result = assign_bidding(
            work_ids=work_ids,
            researchers=researchers,
            existing=existing,
            rng=rng,
        )

        for researcher_id, assigned in result.items():
            repo.save_bidding(set_id, Bidding(researcher_id=researcher_id, work_ids=sorted(assigned)))

        # Compute overlap (papers assigned to 2+ researchers)
        n = len(work_ids)
        overlap_count = sum(
            1 for w in work_ids if sum(1 for ids in result.values() if w in ids) >= 2
        )
        overlap_pct = round(overlap_count / n * 100, 1) if n else 0.0

        summaries.append(BiddingRunSummary(
            set_id=set_id,
            total_works=n,
            per_researcher={r: len(ids) for r, ids in result.items()},
            overlap_pct=overlap_pct,
        ))

    return summaries
