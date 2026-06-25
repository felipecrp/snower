import pytest

from snower import Assessment, Criterion, CriterionType, PaperRepository, Phase, ReviewRepository, parse_bibtex

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


class DescribeReviewRepository:
    def _assessment(self, criterion_id="ic1", criterion_type=CriterionType.inclusion):
        return Assessment(
            criterion=Criterion(id=criterion_id, name="Test", type=criterion_type),
            phase=Phase(id="title", name="Title screening"),
        )

    def it_writes_one_file_per_researcher(self, tmp_path):
        repo = ReviewRepository(tmp_path)
        assessments = {
            "a@b.com": {"paper1": self._assessment()},
            "b@b.com": {"paper2": self._assessment("ec1", CriterionType.exclusion)},
        }
        repo.save_all(assessments)
        assert (tmp_path / "a@b.com.yml").exists()
        assert (tmp_path / "b@b.com.yml").exists()

    def it_round_trips_email_stem_and_contents(self, tmp_path):
        repo = ReviewRepository(tmp_path)
        original = {"a@b.com": {"paper1": self._assessment()}}
        repo.save_all(original)
        criteria = [Criterion(id="ic1", name="Test", type=CriterionType.inclusion)]
        phases = [Phase(id="title", name="Title screening")]
        loaded = repo.load_all(criteria=criteria, phases=phases)
        assert "a@b.com" in loaded
        assert "paper1" in loaded["a@b.com"]
        assert loaded["a@b.com"]["paper1"].criterion.id == "ic1"
        assert loaded["a@b.com"]["paper1"].included is True

    def it_clears_stale_files_on_save(self, tmp_path):
        repo = ReviewRepository(tmp_path)
        repo.save_all({"a@b.com": {"p": self._assessment()}})
        # save again without a@b.com — their file should disappear
        repo.save_all({"b@b.com": {"p": self._assessment()}})
        assert not (tmp_path / "a@b.com.yml").exists()
        assert (tmp_path / "b@b.com.yml").exists()

    def it_skips_researchers_with_no_assessments(self, tmp_path):
        repo = ReviewRepository(tmp_path)
        repo.save_all({"a@b.com": {}})
        assert not (tmp_path / "a@b.com.yml").exists()

    def it_sorts_bib_ids_within_a_file(self, tmp_path):
        import yaml

        repo = ReviewRepository(tmp_path)
        repo.save_all({"a@b.com": {
            "z_paper": self._assessment(),
            "a_paper": self._assessment(),
        }})
        raw = yaml.safe_load((tmp_path / "a@b.com.yml").read_text())
        assert list(raw.keys()) == ["a_paper", "z_paper"]

    def it_writes_slim_format_with_ids_only(self, tmp_path):
        import yaml

        repo = ReviewRepository(tmp_path)
        repo.save_all({"a@b.com": {"paper1": self._assessment()}})
        raw = yaml.safe_load((tmp_path / "a@b.com.yml").read_text())
        assert raw["paper1"] == {"criterion_id": "ic1", "phase_id": "title"}
