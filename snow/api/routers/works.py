"""Works endpoints — read and update individual work BibTeX."""

from __future__ import annotations

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from snow.api.state import get_repo
from snow.domain.identity import WorkRef, full_fingerprint, short_fingerprint
from snow.domain.models import Work
from snow.storage import bib as bib_module
from snow.storage.repo import KeyEntry, ProjectRepo

router = APIRouter(prefix="/api/works", tags=["works"])


class BibtexResponse(BaseModel):
    bibtex: str


class BibtexInput(BaseModel):
    bibtex: str


def _work_ref(w: Work) -> WorkRef:
    return WorkRef(title=w.title, year=w.year, authors=tuple(w.authors))


@router.get("/{bib_key}/bibtex", response_model=BibtexResponse)
def get_bibtex(bib_key: str, repo: ProjectRepo = Depends(get_repo)) -> BibtexResponse:
    path = repo.work_path(bib_key)
    if not path.exists():
        raise HTTPException(404, f"Work not found: {bib_key}")
    return BibtexResponse(bibtex=path.read_text(encoding="utf-8"))


@router.put("/{bib_key}/bibtex", response_model=Work)
def put_bibtex(
    bib_key: str,
    body: BibtexInput,
    repo: ProjectRepo = Depends(get_repo),
) -> Work:
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.customization = convert_to_unicode
    try:
        db = bibtexparser.loads(body.bibtex, parser=parser)
    except Exception as exc:
        raise HTTPException(400, detail={"error": "parse", "message": str(exc)}) from exc

    if not db.entries:
        raise HTTPException(400, detail={"error": "parse", "message": "No BibTeX entries found."})

    entry = dict(db.entries[0])
    entry["ID"] = bib_key

    if not entry.get("title", "").strip():
        raise HTTPException(400, detail={"error": "validation", "message": "Entry must have a non-empty title."})

    work = bib_module._entry_to_work(entry)
    repo.save_work(work)

    keys = repo.load_keys()
    ref = _work_ref(work)
    new_full = full_fingerprint(ref)
    new_short = short_fingerprint(ref)
    if new_full not in keys:
        keys[new_full] = KeyEntry(short=new_short, bib_key=bib_key)
        repo.save_keys(keys)

    return work
