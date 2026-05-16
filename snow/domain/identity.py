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
import unicodedata
from dataclasses import dataclass

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


_MIN_SLUG_WORD_LEN = 5  # words with 4 or fewer chars are skipped (common short / stopwords)


def _title_slug(title: str | None, n_words: int = 2) -> str:
    """First `n_words` long-enough tokens of the normalized title, joined."""
    normalized = normalize_title(title or "")
    if not normalized:
        return ""
    tokens = [w for w in normalized.split() if len(w) >= _MIN_SLUG_WORD_LEN]
    if not tokens:
        # Title has no long-enough words; fall back to whatever is there.
        tokens = normalized.split()
    return "".join(tokens[:n_words])


def _title_hash(title: str | None, length: int = 4) -> str:
    """Short hex digest of the normalized title, used to disambiguate collisions."""
    payload = normalize_title(title or "").encode()
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()[:length]


def mint_bib_key(ref: WorkRef, taken: set[str]) -> str:
    """Return a unique BibTeX key for `ref`, avoiding any string in `taken`.

    Pattern: `<surname><year><slug>` where `slug` is the first two title words
    of 5+ chars. Falls back to `anon` / `nd` / `untitled` when fields are
    missing. On collision with a different work, appends `_<hash4>`
    (deterministic from the full title) so two clients minting the same paper
    concurrently arrive at the same key.
    """
    surname = normalize_author_surname(ref.authors[0]) if ref.authors else "anon"
    surname = surname or "anon"
    year = str(ref.year) if ref.year else "nd"
    slug = _title_slug(ref.title) or "untitled"
    base = f"{surname}{year}{slug}"
    if base not in taken:
        return base
    return f"{base}_{_title_hash(ref.title)}"
