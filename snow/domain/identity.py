"""Stable identity for bibliographic works.

A `work_id` is a deterministic string derived from a bibliographic entry.
It is used to deduplicate the same article across sets and providers.

The ID is a SHA-1 hash of a normalized tuple (first author surname, year, title).
DOI is intentionally kept as metadata, not identity, so enrichment can add it
later without changing existing decisions or relations.
"""

from __future__ import annotations

import hashlib
import re
import string
import unicodedata
from dataclasses import dataclass
from typing import Iterator

_DOI_URL_PREFIX = re.compile(r"^(?:https?://)?(?:dx\.)?doi\.org/", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class WorkRef:
    """Minimal info needed to compute a stable work_id."""

    title: str | None = None
    year: int | None = None
    authors: tuple[str, ...] = ()
    doi: str | None = None


@dataclass(frozen=True)
class BibliographicWork:
    """Provider result with identity fields plus optional bibliographic metadata."""

    title: str | None = None
    year: int | None = None
    authors: tuple[str, ...] = ()
    doi: str | None = None
    venue: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    abstract: str | None = None

    def ref(self) -> WorkRef:
        return WorkRef(title=self.title, year=self.year, authors=self.authors, doi=self.doi)


def normalize_doi(doi: str) -> str:
    return _DOI_URL_PREFIX.sub("", doi).strip().lower()


def normalize_title(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = _NON_ALNUM.sub(" ", folded.lower())
    return _WHITESPACE.sub(" ", folded).strip()


def normalize_author_surname(author: str) -> str:
    """Extract surname from "Last, First" or "First Last" and normalize."""
    author = author.strip()
    if not author:
        return ""
    surname = author.split(",", 1)[0] if "," in author else author.rsplit(" ", 1)[-1]
    folded = unicodedata.normalize("NFKD", surname)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return _NON_ALNUM.sub("", folded.lower())


def work_id(ref: WorkRef) -> str:
    surname = normalize_author_surname(ref.authors[0]) if ref.authors else ""
    title = normalize_title(ref.title or "")
    year = str(ref.year) if ref.year else ""

    payload = f"{surname}|{year}|{title}".encode()
    digest = hashlib.sha1(payload, usedforsecurity=False).hexdigest()[:16]
    return f"sha1:{digest}"


def _letter_suffixes() -> Iterator[str]:
    """Yield 'a', 'b', ..., 'z', 'aa', 'ab', ... for disambiguation."""
    for letter in string.ascii_lowercase:
        yield letter
    for first in string.ascii_lowercase:
        for second in string.ascii_lowercase:
            yield first + second


def mint_bib_key(ref: WorkRef, taken: set[str]) -> str:
    """Return a unique BibTeX key for `ref`, avoiding any string in `taken`.

    Pattern: `<surname><year><letter>`. Falls back to `anon` (no author) and
    `nd` (no year). Letter suffix grows as `a..z, aa..zz` on collision.
    """
    surname = normalize_author_surname(ref.authors[0]) if ref.authors else "anon"
    surname = surname or "anon"
    year = str(ref.year) if ref.year else "nd"
    base = f"{surname}{year}"
    for suffix in _letter_suffixes():
        candidate = f"{base}{suffix}"
        if candidate not in taken:
            return candidate
    raise RuntimeError(f"Exhausted disambiguation suffixes for base={base!r}")
