from snow.domain.identity import (
    WorkRef,
    mint_bib_key,
    normalize_author_surname,
    normalize_doi,
    normalize_title,
    work_id,
)


class DescribeNormalizeDoi:
    def it_strips_url_prefix(self):
        assert normalize_doi("https://doi.org/10.1145/2601248.2601268") == "10.1145/2601248.2601268"

    def it_strips_dx_prefix(self):
        assert normalize_doi("http://dx.doi.org/10.1145/X") == "10.1145/x"

    def it_lowercases(self):
        assert normalize_doi("10.1145/ABCDEF") == "10.1145/abcdef"


class DescribeNormalizeTitle:
    def it_lowercases_and_strips(self):
        assert normalize_title("  Hello World  ") == "hello world"

    def it_removes_punctuation(self):
        assert normalize_title("Hello, World!") == "hello world"

    def it_collapses_whitespace(self):
        assert normalize_title("Hello   \t  World") == "hello world"

    def it_folds_accents(self):
        assert normalize_title("Análise de Citações") == "analise de citacoes"


class DescribeNormalizeAuthorSurname:
    def it_parses_last_comma_first(self):
        assert normalize_author_surname("Wohlin, Claus") == "wohlin"

    def it_parses_first_last(self):
        assert normalize_author_surname("Claus Wohlin") == "wohlin"

    def it_folds_accents(self):
        assert normalize_author_surname("Müller, Hans") == "muller"

    def it_returns_empty_for_blank(self):
        assert normalize_author_surname("   ") == ""


class DescribeWorkId:
    def it_ignores_doi_when_available(self):
        ref = WorkRef(doi="10.1145/X", title="Whatever", authors=("Someone",), year=2020)
        without_doi = WorkRef(title="Whatever", authors=("Someone",), year=2020)
        assert work_id(ref) == work_id(without_doi)

    def it_uses_metadata_even_when_doi_exists(self):
        with_doi = WorkRef(doi="10.1/A", title="T", authors=("A",), year=2020)
        only_meta = WorkRef(title="T", authors=("A",), year=2020)
        assert work_id(with_doi) == work_id(only_meta)

    class DescribeWithoutDoi:
        def it_is_stable_across_capitalization(self):
            a = WorkRef(title="Snowballing Studies", authors=("Wohlin, Claus",), year=2014)
            b = WorkRef(title="SNOWBALLING STUDIES", authors=("wohlin, claus",), year=2014)
            assert work_id(a) == work_id(b)

        def it_is_stable_across_author_format(self):
            a = WorkRef(title="X", authors=("Wohlin, Claus",), year=2014)
            b = WorkRef(title="X", authors=("Claus Wohlin",), year=2014)
            assert work_id(a) == work_id(b)

        def it_differs_when_year_differs(self):
            a = WorkRef(title="X", authors=("A",), year=2014)
            b = WorkRef(title="X", authors=("A",), year=2015)
            assert work_id(a) != work_id(b)

        def it_has_sha1_prefix(self):
            ref = WorkRef(title="X", authors=("A",), year=2014)
            assert work_id(ref).startswith("sha1:")


class DescribeMintBibKey:
    def it_uses_first_two_long_title_words(self):
        ref = WorkRef(
            title="Snowballing in systematic literature reviews",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        assert mint_bib_key(ref, taken=set()) == "wohlin2014snowballingsystematic"

    def it_skips_words_with_four_or_fewer_chars(self):
        ref = WorkRef(
            title="Case study research and data in software engineering",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        # "case" (4), "and" (3), "data" (4), "in" (2) are skipped.
        assert mint_bib_key(ref, taken=set()) == "wohlin2014studyresearch"

    def it_appends_short_hash_on_collision(self):
        ref = WorkRef(
            title="Snowballing in systematic literature reviews",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        taken = {"wohlin2014snowballingsystematic"}
        key = mint_bib_key(ref, taken=taken)
        assert key.startswith("wohlin2014snowballingsystematic_")
        assert len(key.split("_")[-1]) == 4

    def it_falls_back_to_untitled_when_no_title(self):
        ref = WorkRef(title=None, authors=("Wohlin, Claus",), year=2014)
        assert mint_bib_key(ref, taken=set()) == "wohlin2014untitled"

    def it_uses_anon_when_no_authors(self):
        ref = WorkRef(title="Systematic literature review", year=2014)
        assert mint_bib_key(ref, taken=set()) == "anon2014systematicliterature"

    def it_uses_nd_when_no_year(self):
        ref = WorkRef(title="Systematic literature review", authors=("Wohlin, Claus",))
        assert mint_bib_key(ref, taken=set()) == "wohlinndsystematicliterature"

    def it_normalizes_author_surname_for_key(self):
        ref = WorkRef(title="Systematic review", authors=("Müller, Hans",), year=2020)
        assert mint_bib_key(ref, taken=set()) == "muller2020systematicreview"

    def it_uses_short_words_as_fallback_when_no_long_ones(self):
        ref = WorkRef(title="A B C D", authors=("Wohlin, Claus",), year=2014)
        assert mint_bib_key(ref, taken=set()) == "wohlin2014ab"
