"""Tabular (CSV/TSV) parser for imports.

Supported formats:
  csv-doi   — comma-separated, cols: doi [, decision [, phase]]
  csv-meta  — comma-separated, cols: title, authors, year [, decision [, phase]]
  tsv-doi   — tab-separated versions of the above
  tsv-meta
"""

from __future__ import annotations

import csv
import io
import re

from snow.domain.models import Work


def parse(text: str, fmt: str) -> list[Work]:
    """Parse *text* in the given tabular format into Work objects."""
    parts = fmt.split("-", 1)
    if len(parts) != 2 or parts[0] not in ("csv", "tsv") or parts[1] not in ("doi", "meta"):
        raise ValueError(f"Unknown import format: {fmt!r}")

    delimiter = "," if parts[0] == "csv" else "\t"
    mode = parts[1]

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    works: list[Work] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        work = _row_to_work([c.strip() for c in row], mode)
        if work is not None:
            works.append(work)
    return works


_DOI_URL_PREFIX = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)


def _normalize_doi_input(value: str) -> str:
    return _DOI_URL_PREFIX.sub("", value).strip()


def _row_to_work(row: list[str], mode: str) -> Work | None:
    if mode == "doi":
        doi = _normalize_doi_input(row[0]) if row else ""
        if not doi:
            return None
        decision = row[1] if len(row) > 1 else ""
        phase = row[2] if len(row) > 2 else ""
        extra = _groups_extra(decision, phase)
        return Work(bib_key="", title="", doi=doi, extra=extra)

    # mode == "meta"
    title = row[0] if row else ""
    if not title:
        return None
    authors_raw = row[1] if len(row) > 1 else ""
    year_str = row[2] if len(row) > 2 else ""
    decision = row[3] if len(row) > 3 else ""
    phase = row[4] if len(row) > 4 else ""

    authors = _split_authors(authors_raw) if authors_raw else []
    year = int(year_str) if year_str.isdigit() else None
    extra = _groups_extra(decision, phase)
    return Work(bib_key="", title=title, authors=authors, year=year, extra=extra)


def _groups_extra(decision: str, phase: str) -> dict[str, str]:
    groups = ",".join(v for v in [decision, phase] if v)
    return {"groups": groups} if groups else {}


def _split_authors(raw: str) -> list[str]:
    parts = re.split(r";| and ", raw)
    return [p.strip() for p in parts if p.strip()]
