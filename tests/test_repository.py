import pytest

from snower import PaperRepository, parse_bibtex

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
"""

_BIB_INCOMPLETE = """\
@article{noauthor2024,
  title = {A Title Without Author},
  year = {2024},
}
"""


class DescribePaperRepository:
    def it_writes_a_file_named_after_bib_id(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        repo = PaperRepository(tmp_path)
        repo.save(paper)
        assert (tmp_path / "kitchenham2009systematic.yml").exists()

    def it_round_trips_a_paper(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        repo = PaperRepository(tmp_path)
        repo.save(paper)
        loaded = repo.load(paper.bib_id)
        assert loaded == paper

    def it_loads_all_papers(self, tmp_path):
        papers = parse_bibtex(_BIB)
        repo = PaperRepository(tmp_path)
        for p in papers:
            repo.save(p)
        loaded = repo.load_all()
        assert len(loaded) == 2
        assert {p.bib_id for p in loaded} == {p.bib_id for p in papers}

    def it_raises_when_bib_id_missing(self, tmp_path):
        papers = parse_bibtex(_BIB_INCOMPLETE)
        repo = PaperRepository(tmp_path)
        with pytest.raises(ValueError, match="bib_id"):
            repo.save(papers[0])

    def it_raises_when_authors_missing(self, tmp_path):
        papers = parse_bibtex(_BIB_INCOMPLETE)
        repo = PaperRepository(tmp_path)
        with pytest.raises(ValueError, match="authors"):
            repo.save(papers[0])

    def it_raises_when_year_missing(self, tmp_path):
        from snower.paper import Author, Paper

        paper = Paper(title="No Year", authors=[Author(family="Smith")], bib_id="smith2000test")
        repo = PaperRepository(tmp_path)
        with pytest.raises(ValueError, match="year"):
            repo.save(paper)

    def it_creates_the_directory_if_absent(self, tmp_path):
        paper = parse_bibtex(_BIB)[0]
        repo = PaperRepository(tmp_path / "subdir" / "papers")
        repo.save(paper)
        assert (tmp_path / "subdir" / "papers" / "kitchenham2009systematic.yml").exists()
