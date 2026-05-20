import pytest

from snow.storage.tabular import parse


class DescribeParseCSVDoi:
    def it_parses_doi_only(self):
        works = parse("10.1234/foo\n10.1234/bar\n", "csv-doi")
        assert len(works) == 2
        assert works[0].doi == "10.1234/foo"
        assert works[1].doi == "10.1234/bar"

    def it_skips_blank_rows(self):
        works = parse("10.1234/foo\n\n10.1234/bar\n", "csv-doi")
        assert len(works) == 2

    def it_stores_decision_and_phase_in_groups(self):
        works = parse("10.1234/foo,ic1,ph1\n", "csv-doi")
        assert works[0].extra.get("groups") == "ic1,ph1"

    def it_stores_only_decision_when_phase_absent(self):
        works = parse("10.1234/foo,ic1\n", "csv-doi")
        assert works[0].extra.get("groups") == "ic1"

    def it_sets_no_groups_when_trailing_cols_empty(self):
        works = parse("10.1234/foo,,\n", "csv-doi")
        assert "groups" not in works[0].extra

    def it_skips_rows_with_empty_doi(self):
        works = parse(",ic1\n", "csv-doi")
        assert works == []

    def it_strips_doi_org_url_prefix(self):
        works = parse("https://doi.org/10.1145/146628.139676\n", "csv-doi")
        assert works[0].doi == "10.1145/146628.139676"

    def it_strips_dx_doi_org_url_prefix(self):
        works = parse("https://dx.doi.org/10.1145/146628.139676\n", "csv-doi")
        assert works[0].doi == "10.1145/146628.139676"


class DescribeParseCSVMeta:
    def it_parses_title_authors_year(self):
        works = parse("A Study,Doe J;Smith K,2021\n", "csv-meta")
        assert len(works) == 1
        w = works[0]
        assert w.title == "A Study"
        assert w.year == 2021
        assert "Doe J" in w.authors
        assert "Smith K" in w.authors

    def it_handles_authors_split_by_and(self):
        works = parse("Title,Doe J and Smith K,2020\n", "csv-meta")
        assert len(works[0].authors) == 2

    def it_handles_missing_year(self):
        works = parse("Title,Doe J,\n", "csv-meta")
        assert works[0].year is None

    def it_stores_decision_and_phase_in_groups(self):
        works = parse("Title,Doe J,2020,ic1,ph1\n", "csv-meta")
        assert works[0].extra.get("groups") == "ic1,ph1"

    def it_skips_rows_with_empty_title(self):
        works = parse(",Doe J,2020\n", "csv-meta")
        assert works == []


class DescribeParseTSVDoi:
    def it_parses_tab_delimited_doi(self):
        works = parse("10.1234/foo\n10.1234/bar\n", "tsv-doi")
        assert len(works) == 2
        assert works[0].doi == "10.1234/foo"

    def it_stores_decision_and_phase_in_groups(self):
        works = parse("10.1234/foo\tic1\tph1\n", "tsv-doi")
        assert works[0].extra.get("groups") == "ic1,ph1"


class DescribeParseTSVMeta:
    def it_parses_tab_delimited_meta(self):
        works = parse("My Title\tDoe J\t2022\n", "tsv-meta")
        assert works[0].title == "My Title"
        assert works[0].year == 2022


class DescribeParseInvalidFormat:
    def it_raises_on_unknown_format(self):
        with pytest.raises(ValueError, match="Unknown import format"):
            parse("data", "xml")


class DescribeDOIValidation:
    def it_raises_on_invalid_doi_format(self):
        with pytest.raises(ValueError, match="invalid DOI format"):
            parse("not-a-doi\n", "csv-doi")

    def it_includes_row_number_in_error(self):
        with pytest.raises(ValueError, match="Row 2"):
            parse("10.1234/valid\nbad-doi\n", "csv-doi")

    def it_accepts_doi_with_slash(self):
        works = parse("10.1234/some-suffix\n", "csv-doi")
        assert works[0].doi == "10.1234/some-suffix"

    def it_accepts_doi_with_dot_separator(self):
        works = parse("10.1234.some-suffix\n", "csv-doi")
        assert works[0].doi == "10.1234.some-suffix"
