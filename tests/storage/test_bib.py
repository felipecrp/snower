from pathlib import Path

from snow.domain.models import Work
from snow.storage import bib

SAMPLE_BIB = """
@inproceedings{wohlin2014,
    author = {Wohlin, Claus},
    title = {Guidelines for snowballing in systematic literature studies},
    year = {2014},
    booktitle = {EASE},
    doi = {10.1145/2601248.2601268}
}

@article{kitchenham2007,
    author = {Kitchenham, Barbara and Charters, Stuart},
    title = {Guidelines for performing systematic literature reviews},
    year = {2007},
    journal = {Keele University}
}
"""


class DescribeBibLoad:
    def it_returns_empty_list_for_missing_file(self, tmp_path: Path):
        assert bib.load(tmp_path / "nope.bib") == []

    def it_parses_entries_into_works(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(SAMPLE_BIB)
        works = bib.load(path)
        assert len(works) == 2

    def it_splits_multiple_authors(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(SAMPLE_BIB)
        works = bib.load(path)
        kitchenham = next(w for w in works if w.bib_key == "kitchenham2007")
        assert kitchenham.authors == ["Kitchenham, Barbara", "Charters, Stuart"]

    def it_maps_booktitle_to_venue(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(SAMPLE_BIB)
        works = bib.load(path)
        wohlin = next(w for w in works if w.bib_key == "wohlin2014")
        assert wohlin.venue == "EASE"

    def it_parses_pdf_url(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(
            "@article{x, title = {X}, year = {2020}, pdf_url = {https://example.com/x.pdf}}\n"
        )
        works = bib.load(path)
        assert works[0].pdf_url == "https://example.com/x.pdf"


class DescribeBibLatexDecoding:
    def it_decodes_latex_accents(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(
            '@article{mantyla2013, '
            'author = {M{\\"a}ntyl{\\"a}, Mika V and Engstr{\\"o}m, Emelie}, '
            'title = {Testing}, '
            'year = {2013}}\n'
        )
        works = bib.load(path)
        assert works[0].authors == ["Mäntylä, Mika V", "Engström, Emelie"]

    def it_decodes_escaped_specials(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(
            "@article{x, author = {A, A}, title = {Foo \\& Bar 100\\%}, year = {2020}}\n"
        )
        works = bib.load(path)
        assert works[0].title == "Foo & Bar 100%"

    def it_preserves_existing_unicode(self, tmp_path: Path):
        path = tmp_path / "in.bib"
        path.write_text(
            "@article{x, author = {Müller, Hans}, title = {Citações}, year = {2020}}\n",
            encoding="utf-8",
        )
        works = bib.load(path)
        assert works[0].authors == ["Müller, Hans"]
        assert works[0].title == "Citações"


class DescribeBibDump:
    def it_round_trips_through_load_dump_load(self, tmp_path: Path):
        path = tmp_path / "round.bib"
        path.write_text(SAMPLE_BIB)
        original = bib.load(path)

        out = tmp_path / "out.bib"
        bib.dump(original, out)
        reloaded = bib.load(out)

        assert len(reloaded) == len(original)
        original_by_key = {w.bib_key: w for w in original}
        for w in reloaded:
            o = original_by_key[w.bib_key]
            assert w.title == o.title
            assert w.authors == o.authors
            assert w.year == o.year
            assert w.doi == o.doi
            assert w.pdf_url == o.pdf_url

    def it_emits_entries_sorted_by_key(self, tmp_path: Path):
        works = [
            Work(bib_key="zeta2020", title="Z", authors=["Z, Z"]),
            Work(bib_key="alpha2020", title="A", authors=["A, A"]),
        ]
        out = tmp_path / "out.bib"
        bib.dump(works, out)
        text = out.read_text()
        assert text.index("alpha2020") < text.index("zeta2020")

    def it_dumps_pdf_url(self, tmp_path: Path):
        works = [
            Work(bib_key="x2020", title="X", authors=["X, X"], pdf_url="https://example.com/x.pdf"),
        ]
        out = tmp_path / "out.bib"
        bib.dump(works, out)
        text = out.read_text()
        assert "pdf_url = {https://example.com/x.pdf}" in text
