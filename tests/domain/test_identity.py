from snow.domain.identity import (
    WorkRef,
    full_fingerprint,
    mint_bib_key,
    normalize_author_surname,
    normalize_doi,
    normalize_title,
    short_fingerprint,
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


class DescribeFullFingerprint:
    def it_uses_all_authors(self):
        one = WorkRef(title="T", authors=("A, X",), year=2020)
        two = WorkRef(title="T", authors=("A, X", "B, Y"), year=2020)
        assert full_fingerprint(one) != full_fingerprint(two)

    def it_uses_full_title(self):
        a = WorkRef(title="Snowballing systematic", authors=("Wohlin, Claus",), year=2014)
        b = WorkRef(title="Snowballing in systematic literature reviews", authors=("Wohlin, Claus",), year=2014)
        assert full_fingerprint(a) != full_fingerprint(b)

    def it_is_stable_across_capitalization(self):
        a = WorkRef(title="Snowballing Studies", authors=("Wohlin, Claus",), year=2014)
        b = WorkRef(title="SNOWBALLING STUDIES", authors=("wohlin, claus",), year=2014)
        assert full_fingerprint(a) == full_fingerprint(b)

    def it_differs_when_year_differs(self):
        a = WorkRef(title="X", authors=("A",), year=2014)
        b = WorkRef(title="X", authors=("A",), year=2015)
        assert full_fingerprint(a) != full_fingerprint(b)

    def it_has_sha1full_prefix(self):
        ref = WorkRef(title="X", authors=("A",), year=2014)
        assert full_fingerprint(ref).startswith("sha1full:")

    def it_does_not_use_doi(self):
        # DOI removed from WorkRef — same title/year/authors always gives same fingerprint
        a = WorkRef(title="Whatever", authors=("Someone",), year=2020)
        b = WorkRef(title="Whatever", authors=("Someone",), year=2020)
        assert full_fingerprint(a) == full_fingerprint(b)


class DescribeShortFingerprint:
    def it_uses_only_first_two_authors(self):
        two = WorkRef(title="T", authors=("A, X", "B, Y"), year=2020)
        three = WorkRef(title="T", authors=("A, X", "B, Y", "C, Z"), year=2020)
        assert short_fingerprint(two) == short_fingerprint(three)

    def it_uses_three_significant_title_words(self):
        a = WorkRef(title="Systematic literature review methods", authors=("A",), year=2020)
        b = WorkRef(title="Systematic literature review approaches", authors=("A",), year=2020)
        # Only first 3 words (systematic, literature, review) are used → same
        assert short_fingerprint(a) == short_fingerprint(b)

    def it_differs_on_first_three_words(self):
        a = WorkRef(title="Systematic review methods", authors=("A",), year=2020)
        b = WorkRef(title="Systematic survey methods", authors=("A",), year=2020)
        assert short_fingerprint(a) != short_fingerprint(b)

    def it_has_sha1short_prefix(self):
        ref = WorkRef(title="X", authors=("A",), year=2014)
        assert short_fingerprint(ref).startswith("sha1short:")

    def it_has_8_char_hex_suffix(self):
        ref = WorkRef(title="Some long title here", authors=("A",), year=2014)
        suffix = short_fingerprint(ref).removeprefix("sha1short:")
        assert len(suffix) == 8


class DescribeMintBibKey:
    def it_uses_first_significant_title_word(self):
        ref = WorkRef(
            title="Snowballing in systematic literature reviews",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        assert mint_bib_key(ref, taken=set()) == "wohlin2014snowballing"

    def it_skips_words_with_four_or_fewer_chars(self):
        ref = WorkRef(
            title="Case study research and data in software engineering",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        # "case" (4) skipped; "study" (5) is the first significant word
        assert mint_bib_key(ref, taken=set()) == "wohlin2014study"

    def it_appends_sequential_number_on_collision(self):
        ref = WorkRef(
            title="Snowballing in systematic literature reviews",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        taken = {"wohlin2014snowballing"}
        assert mint_bib_key(ref, taken=taken) == "wohlin2014snowballing2"

    def it_increments_sequential_number_past_existing(self):
        ref = WorkRef(
            title="Snowballing in systematic literature reviews",
            authors=("Wohlin, Claus",),
            year=2014,
        )
        taken = {"wohlin2014snowballing", "wohlin2014snowballing2"}
        assert mint_bib_key(ref, taken=taken) == "wohlin2014snowballing3"

    def it_falls_back_to_untitled_when_no_title(self):
        ref = WorkRef(title=None, authors=("Wohlin, Claus",), year=2014)
        assert mint_bib_key(ref, taken=set()) == "wohlin2014untitled"

    def it_uses_anon_when_no_authors(self):
        ref = WorkRef(title="Systematic literature review", year=2014)
        assert mint_bib_key(ref, taken=set()) == "anon2014systematic"

    def it_uses_nd_when_no_year(self):
        ref = WorkRef(title="Systematic literature review", authors=("Wohlin, Claus",))
        assert mint_bib_key(ref, taken=set()) == "wohlinndsystematic"

    def it_normalizes_author_surname_for_key(self):
        ref = WorkRef(title="Systematic review", authors=("Müller, Hans",), year=2020)
        assert mint_bib_key(ref, taken=set()) == "muller2020systematic"

    def it_uses_short_words_as_fallback_when_no_long_ones(self):
        ref = WorkRef(title="A B C D", authors=("Wohlin, Claus",), year=2014)
        assert mint_bib_key(ref, taken=set()) == "wohlin2014a"
