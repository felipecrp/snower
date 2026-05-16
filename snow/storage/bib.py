"""BibTeX reader/writer.

Converts between on-disk `.bib` files and the `Work` domain model. Each
parsed entry gets a `work_id` computed from `snow.domain.identity`.
"""

from __future__ import annotations

from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

from snow.domain.identity import WorkRef, work_id
from snow.domain.models import Work

_KNOWN_FIELDS = {"title", "author", "year", "journal", "booktitle", "doi", "url", "abstract"}


def _split_authors(raw: str) -> list[str]:
    return [a.strip() for a in raw.split(" and ") if a.strip()]


def _entry_to_work(entry: dict[str, str]) -> Work:
    authors = _split_authors(entry.get("author", ""))
    year_str = entry.get("year", "").strip()
    year = int(year_str) if year_str.isdigit() else None
    venue = entry.get("journal") or entry.get("booktitle")
    doi = entry.get("doi") or None

    ref = WorkRef(
        title=entry.get("title"),
        year=year,
        authors=tuple(authors),
        doi=doi,
    )
    extra = {k: v for k, v in entry.items() if k not in _KNOWN_FIELDS and k not in {"ID", "ENTRYTYPE"}}

    return Work(
        id=work_id(ref),
        bib_key=entry["ID"],
        title=entry.get("title", "").strip(),
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        url=entry.get("url"),
        abstract=entry.get("abstract"),
        extra=extra,
    )


def _work_to_entry(work: Work, entry_type: str = "article") -> dict[str, str]:
    entry: dict[str, str] = {
        "ENTRYTYPE": entry_type,
        "ID": work.bib_key,
        "title": work.title,
    }
    if work.authors:
        entry["author"] = " and ".join(work.authors)
    if work.year is not None:
        entry["year"] = str(work.year)
    if work.venue:
        entry["journal"] = work.venue
    if work.doi:
        entry["doi"] = work.doi
    if work.url:
        entry["url"] = work.url
    if work.abstract:
        entry["abstract"] = work.abstract
    entry.update(work.extra)
    return entry


def load(path: Path) -> list[Work]:
    if not path.exists():
        return []
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.customization = convert_to_unicode
    with path.open("r", encoding="utf-8") as f:
        db = bibtexparser.load(f, parser=parser)
    return [_entry_to_work(e) for e in db.entries]


def dump(works: list[Work], path: Path) -> None:
    db = BibDatabase()
    db.entries = [_work_to_entry(w) for w in works]
    writer = BibTexWriter()
    writer.indent = "    "
    writer.order_entries_by = ("ID",)
    path.write_text(writer.write(db), encoding="utf-8")
