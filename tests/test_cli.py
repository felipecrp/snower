from pathlib import Path

from typer.testing import CliRunner

from snow.cli import app
from snow.storage.repo import ProjectRepo

runner = CliRunner()

SAMPLE_BIB = """
@inproceedings{wohlin2014,
    author = {Wohlin, Claus},
    title = {Guidelines for snowballing},
    year = {2014},
    booktitle = {EASE},
    doi = {10.1145/2601248.2601268}
}
"""


class DescribeInit:
    def it_creates_a_new_project(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path / "proj")])
        assert result.exit_code == 0
        assert (tmp_path / "proj" / "project.yml").exists()
        project = ProjectRepo(tmp_path / "proj").load_project()
        assert project.name == "proj"

    def it_honors_explicit_name(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path / "p"), "--name", "My Review"])
        assert result.exit_code == 0
        assert ProjectRepo(tmp_path / "p").load_project().name == "My Review"

    def it_refuses_to_overwrite_existing_project(self, tmp_path: Path):
        runner.invoke(app, ["init", str(tmp_path / "p")])
        result = runner.invoke(app, ["init", str(tmp_path / "p")])
        assert result.exit_code == 1


class DescribeImportBib:
    def it_imports_into_start_set(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        runner.invoke(app, ["init", str(project_dir)])
        bib_path = tmp_path / "sample.bib"
        bib_path.write_text(SAMPLE_BIB)

        result = runner.invoke(app, ["import-bib", str(bib_path), "-p", str(project_dir)])
        assert result.exit_code == 0
        assert (project_dir / "sets" / "00-start" / "articles.bib").exists()

    def it_fails_when_project_missing(self, tmp_path: Path):
        bib_path = tmp_path / "sample.bib"
        bib_path.write_text(SAMPLE_BIB)
        result = runner.invoke(app, ["import-bib", str(bib_path), "-p", str(tmp_path / "absent")])
        assert result.exit_code == 1

    def it_rejects_rdf_xml_file(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        runner.invoke(app, ["init", str(project_dir)])
        bib_path = tmp_path / "sample.bib"
        bib_path.write_text('<?xml version="1.0"?>\n<rdf:RDF></rdf:RDF>')
        result = runner.invoke(app, ["import-bib", str(bib_path), "-p", str(project_dir)])
        assert result.exit_code == 1
        assert "BibTeX" in result.stderr

    def it_fails_when_zero_entries_parsed(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        runner.invoke(app, ["init", str(project_dir)])
        bib_path = tmp_path / "sample.bib"
        bib_path.write_text("@comment{nothing useful here}\n")
        result = runner.invoke(app, ["import-bib", str(bib_path), "-p", str(project_dir)])
        assert result.exit_code == 1
        assert "0 entries" in result.stderr
