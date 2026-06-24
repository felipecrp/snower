from snower import parse_bibtex

_BIB = """\
@article{kitchenham2009,
  author = {Kitchenham, Barbara},
  title = {Systematic Literature Reviews in Software Engineering},
  year = {2009},
  doi = {10.1234/example},
}

@article{beethoven1827,
  author = {Ludwig van Beethoven and Wolfgang Amadeus Mozart},
  title = {Classical Music Theory},
  year = {1827},
}

@article{barnesandnoble2024,
  author = {{Barnes and Noble}},
  title = {Modern Publishing Trends},
  year = {2024},
}
"""


class DescribeParseBibtex:
    def it_parses_entry_type_and_bib_id(self):
        papers = parse_bibtex(_BIB)
        kitchenham = papers[0]
        assert kitchenham.entry_type == "article"
        assert kitchenham.bib_id == "kitchenham2009systematic"
        assert kitchenham.title == "Systematic Literature Reviews in Software Engineering"
        assert kitchenham.year == 2009

    def it_stores_citation_key(self):
        papers = parse_bibtex(_BIB)
        assert papers[0].fields["bib_key"] == "kitchenham2009"

    def it_maps_von_particle_to_family(self):
        papers = parse_bibtex(_BIB)
        beethoven_paper = papers[1]
        assert beethoven_paper.authors[0].family == "van Beethoven"
        assert beethoven_paper.authors[0].given == "Ludwig"

    def it_handles_braced_atomic_name(self):
        papers = parse_bibtex(_BIB)
        bn_paper = papers[2]
        assert len(bn_paper.authors) == 1
        assert bn_paper.authors[0].family == "Barnes and Noble"

    def it_parses_multiple_authors(self):
        papers = parse_bibtex(_BIB)
        beethoven_paper = papers[1]
        assert len(beethoven_paper.authors) == 2
        assert beethoven_paper.authors[1].family == "Mozart"
