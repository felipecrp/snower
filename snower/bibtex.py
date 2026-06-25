"""BibTeX file parsing utilities for snower."""

from pathlib import Path

import bibtexparser
from bibtexparser.middlewares import LatexDecodingMiddleware, SeparateCoAuthors, SplitNameParts

from snower.paper import Paper, PaperFactory

_LATEX_DECODER = LatexDecodingMiddleware()
_MIDDLEWARES = [SeparateCoAuthors(), SplitNameParts()]


def _decode_latex(text: str) -> str:
    """Decode BibTeX/LaTeX commands into plain text."""
    decoded, _ = _LATEX_DECODER._transform_python_value_string(text)
    return decoded


def _decode_name_part_tokens(tokens: list[str]) -> list[str]:
    return [_decode_latex(token) for token in tokens]


def _decode_entry_latex(entry) -> None:
    """Decode LaTeX left by BibTeX parsing before building Paper objects."""
    for field in entry.fields:
        if isinstance(field.value, str):
            field.value = _decode_latex(field.value)
        elif field.key == "author":
            for parts in field.value:
                parts.first = _decode_name_part_tokens(parts.first)
                parts.von = _decode_name_part_tokens(parts.von)
                parts.last = _decode_name_part_tokens(parts.last)
                parts.jr = _decode_name_part_tokens(parts.jr)


def _papers_from_library(library) -> list[Paper]:
    for entry in library.entries:
        _decode_entry_latex(entry)
    factory = PaperFactory()
    return [factory.from_entry(entry) for entry in library.entries]


def parse_bibtex(text: str) -> list[Paper]:
    """Parse a BibTeX string and return a list of Paper instances."""
    library = bibtexparser.parse_string(text, append_middleware=_MIDDLEWARES)
    return _papers_from_library(library)


def parse_bibtex_file(path: str | Path) -> list[Paper]:
    """Parse a BibTeX file and return a list of Paper instances."""
    library = bibtexparser.parse_file(str(path), append_middleware=_MIDDLEWARES)
    return _papers_from_library(library)
