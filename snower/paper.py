import string
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class EntryType(str, Enum):
    """Standard BibTeX entry types."""

    article = "article"
    book = "book"
    booklet = "booklet"
    conference = "conference"
    inbook = "inbook"
    incollection = "incollection"
    inproceedings = "inproceedings"
    manual = "manual"
    mastersthesis = "mastersthesis"
    misc = "misc"
    phdthesis = "phdthesis"
    proceedings = "proceedings"
    techreport = "techreport"
    unpublished = "unpublished"


class Author(BaseModel):
    """A structured author name with family name, given name, and optional suffix."""

    family: str
    given: str | None = None
    suffix: str | None = None

    @classmethod
    def from_name_parts(cls, parts) -> "Author":
        """Construct an Author from bibtexparser NameParts.

        Maps von + last to family, first to given, and jr to suffix.
        Braces used by bibtexparser to mark atomic tokens are stripped.
        """

        def strip_braces(tokens: list[str]) -> list[str]:
            return [t[1:-1] if t.startswith("{") and t.endswith("}") else t for t in tokens]

        family = " ".join(strip_braces(parts.von + parts.last)) if (parts.von or parts.last) else ""
        given = " ".join(strip_braces(parts.first)) or None
        suffix = " ".join(strip_braces(parts.jr)) or None
        return cls(family=family, given=given, suffix=suffix)


class Paper(BaseModel):
    """A bibliographic paper. Explicit fields cover the most common BibTeX attributes;
    everything else is preserved verbatim in `fields`."""

    entry_type: EntryType = EntryType.misc
    bib_id: str | None = None
    title: str
    authors: list[Author] = []
    year: int | None = None
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    fields: dict[str, str] = {}


class PaperFactory:
    """Constructs Paper instances from raw BibTeX data and computes their bib_id.

    Collision handling will be added here in a future iteration.
    """

    _KNOWN_FIELDS = {"title", "author", "year", "abstract", "doi", "url"}

    @staticmethod
    def _first_relevant_title_word(title: str) -> str | None:
        """Return the first whitespace-delimited title token of length ≥ 5, lowercased and stripped of punctuation."""
        for token in title.split():
            word = token.strip(string.punctuation).lower()
            if len(word) >= 5:
                return word
        return None

    @staticmethod
    def _compute_bib_id(title: str, authors: list[Author], year: int | None) -> str | None:
        """Compute the bib_id as `{first_author_surname}{year}{first_relevant_title_word}`, e.g. `kitchenham2009systematic`."""
        surname = authors[0].family.lower() if authors else None
        title_word = PaperFactory._first_relevant_title_word(title)
        yr = str(year) if year else None
        if not (surname and title_word and yr):
            return None
        return f"{surname}{yr}{title_word}"

    def from_entry(self, entry) -> Paper:
        """Build a Paper from a bibtexparser Entry.

        Expects SeparateCoAuthors and SplitNameParts middlewares applied so that
        the author field value is a list[NameParts].
        """
        authors = []
        str_fields: dict[str, str] = {}

        for field in entry.fields:
            if field.key == "author":
                authors = [Author.from_name_parts(p) for p in field.value]
            else:
                str_fields[field.key] = field.value

        year_raw = str_fields.get("year")
        year = int(year_raw) if year_raw and year_raw.isdigit() else None
        title = str_fields.get("title", "")
        extra = {k: v for k, v in str_fields.items() if k not in self._KNOWN_FIELDS}
        if entry.key:
            extra["bib_key"] = entry.key

        return Paper(
            entry_type=EntryType(entry.entry_type.lower()),
            bib_id=self._compute_bib_id(title, authors, year),
            title=title,
            authors=authors,
            year=year,
            abstract=str_fields.get("abstract"),
            doi=str_fields.get("doi"),
            url=str_fields.get("url"),
            fields=extra,
        )


