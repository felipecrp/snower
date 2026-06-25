"""BibTeX file parsing utilities for snower."""

from pathlib import Path

import bibtexparser
from bibtexparser.middlewares import LatexDecodingMiddleware, SeparateCoAuthors, SplitNameParts

from snower.paper import Paper, PaperFactory

_MIDDLEWARES = [LatexDecodingMiddleware(), SeparateCoAuthors(), SplitNameParts()]


def parse_bibtex(text: str) -> list[Paper]:
    """Parse a BibTeX string and return a list of Paper instances."""
    library = bibtexparser.parse_string(text, append_middleware=_MIDDLEWARES)
    factory = PaperFactory()
    return [factory.from_entry(entry) for entry in library.entries]


def parse_bibtex_file(path: str | Path) -> list[Paper]:
    """Parse a BibTeX file and return a list of Paper instances."""
    library = bibtexparser.parse_file(str(path), append_middleware=_MIDDLEWARES)
    factory = PaperFactory()
    return [factory.from_entry(entry) for entry in library.entries]
