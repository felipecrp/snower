"""Stable identity for bibliographic works.

Two hash functions identify papers:

- `full_fingerprint`: SHA-1 of all authors + year + full title. Near-collision-proof.
  Used as the primary key in keys.yml.

- `short_fingerprint`: SHA-1 of first 2 author surnames + year + first 3 significant title
  words. Fuzzy match — tolerates partial author lists and truncated titles across sources.
  Used to detect the same paper arriving from different providers.

`bib_key` is the human-readable identifier used everywhere in the system (decisions, relations,
file names). It is derived from the first author surname, year, and first significant title
word. keys.yml maps full fingerprints → bib_keys and is the authoritative registry.
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
    """Identity fingerprint input: fields used to recognize the same paper across sources."""

    title: str | None = None
    year: int | None = None
    authors: tuple[str, ...] = ()


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


def full_fingerprint(ref: WorkRef) -> str:
    """SHA-1 of all author surnames + year + full normalized title.

    Near-collision-proof. Used as the primary key in keys.yml.
    """
    surnames = "|".join(normalize_author_surname(a) for a in ref.authors)
    title = normalize_title(ref.title or "")
    year = str(ref.year) if ref.year else ""
    payload = f"{surnames}|{year}|{title}".encode()
    return "sha1full:" + hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def short_fingerprint(ref: WorkRef) -> str:
    """SHA-1 of first 2 author surnames + year + first 3 significant title words.

    Fuzzy match — tolerates partial author lists and truncated/misspelled titles.
    Used to deduplicate the same paper arriving from different providers.
    """
    surnames = "|".join(normalize_author_surname(a) for a in ref.authors[:2])
    title = _title_slug(ref.title, n_words=3)
    year = str(ref.year) if ref.year else ""
    payload = f"{surnames}|{year}|{title}".encode()
    return "sha1short:" + hashlib.sha1(payload, usedforsecurity=False).hexdigest()[:8]


_MIN_SLUG_WORD_LEN = 5  # words with 4 or fewer chars are skipped (common short / stopwords)


def _title_slug(title: str | None, n_words: int = 1) -> str:
    """First `n_words` long-enough tokens of the normalized title, joined."""
    normalized = normalize_title(title or "")
    if not normalized:
        return ""
    tokens = [w for w in normalized.split() if len(w) >= _MIN_SLUG_WORD_LEN]
    if not tokens:
        tokens = normalized.split()
    return "".join(tokens[:n_words])


def mint_bib_key(ref: WorkRef, taken: set[str]) -> str:
    """Return a unique BibTeX key for `ref`, avoiding any string in `taken`.

    Pattern: `<surname><year><word>` where `word` is the first title word with 5+ chars.
    Falls back to `anon` / `nd` / `untitled` when fields are missing.
    On collision appends a sequential number (`2`, `3`, …) until the key is free.
    """
    surname = normalize_author_surname(ref.authors[0]) if ref.authors else "anon"
    surname = surname or "anon"
    year = str(ref.year) if ref.year else "nd"
    slug = _title_slug(ref.title, n_words=1) or "untitled"
    base = f"{surname}{year}{slug}"
    if base not in taken:
        return base
    n = 2
    while True:
        candidate = f"{base}{n}"
        if candidate not in taken:
            return candidate
        n += 1
