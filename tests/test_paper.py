from bibtexparser.middlewares import SeparateCoAuthors, SplitNameParts
from bibtexparser.model import Entry, Field

from snower import Author, EntryType, Paper, PaperFactory


def _make_entry(key: str, entry_type: str, author_str: str | None = None, **kwargs) -> Entry:
    """Helper: build a bibtexparser Entry with SeparateCoAuthors+SplitNameParts applied."""
    import bibtexparser

    fields_str = ""
    if author_str is not None:
        fields_str += f"  author = {{{author_str}}},\n"
    for k, v in kwargs.items():
        fields_str += f"  {k} = {{{v}}},\n"
    bib = f"@{entry_type}{{{key},\n{fields_str}}}"
    lib = bibtexparser.parse_string(
        bib, append_middleware=[SeparateCoAuthors(), SplitNameParts()]
    )
    return lib.entries[0]


class DescribeAuthor:
    def it_maps_last_name_to_family(self):
        entry = _make_entry("k2009", "article", author_str="Kitchenham, Barbara")
        authors = PaperFactory().from_entry(entry).authors
        assert authors[0].family == "Kitchenham"
        assert authors[0].given == "Barbara"

    def it_maps_von_particle_into_family(self):
        entry = _make_entry("b1827", "article", author_str="Ludwig van Beethoven")
        authors = PaperFactory().from_entry(entry).authors
        assert authors[0].family == "van Beethoven"
        assert authors[0].given == "Ludwig"

    def it_handles_suffix(self):
        entry = _make_entry("b1827", "article", author_str="Beethoven, Jr, Ludwig")
        authors = PaperFactory().from_entry(entry).authors
        assert authors[0].family == "Beethoven"
        assert authors[0].suffix == "Jr"
        assert authors[0].given == "Ludwig"

    def it_handles_braced_atomic_name(self):
        entry = _make_entry("bn2024", "article", author_str="{Barnes and Noble}")
        authors = PaperFactory().from_entry(entry).authors
        assert len(authors) == 1
        assert authors[0].family == "Barnes and Noble"


class DescribePaper:
    def it_has_an_identifier(self):
        entry = _make_entry(
            "kitchenham2009",
            "article",
            author_str="Kitchenham, Barbara",
            title="A systematic review of X",
            year="2009",
        )
        paper = PaperFactory().from_entry(entry)
        assert paper.bib_id == "kitchenham2009systematic"

    def it_has_authors_title_and_year(self):
        entry = _make_entry(
            "kitchenham2009",
            "article",
            author_str="Kitchenham, Barbara",
            title="A systematic review of X",
            year="2009",
        )
        paper = PaperFactory().from_entry(entry)
        assert paper.title == "A systematic review of X"
        assert paper.authors[0].family == "Kitchenham"
        assert paper.year == 2009

    def it_has_identifiers(self):
        entry = _make_entry(
            "kitchenham2009",
            "article",
            author_str="Kitchenham, Barbara",
            title="A systematic review of X",
            year="2009",
            doi="10.1234/example",
            url="https://example.com",
        )
        paper = PaperFactory().from_entry(entry)
        assert paper.doi == "10.1234/example"
        assert paper.url == "https://example.com"

    def it_has_other_bibtex_attributes(self):
        entry = _make_entry(
            "kitchenham2009",
            "article",
            author_str="Kitchenham, Barbara",
            title="A systematic review of X",
            year="2009",
            journal="Information and Software Technology",
            volume="51",
        )
        paper = PaperFactory().from_entry(entry)
        assert paper.fields["journal"] == "Information and Software Technology"
        assert paper.fields["volume"] == "51"

    def it_stores_citation_key_in_fields(self):
        entry = _make_entry(
            "kitchenham2009",
            "article",
            author_str="Kitchenham, Barbara",
            title="A systematic review of X",
            year="2009",
        )
        paper = PaperFactory().from_entry(entry)
        assert paper.fields["bib_key"] == "kitchenham2009"
