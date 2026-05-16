from pathlib import Path

from snow.storage import yml


class DescribeYmlDump:
    def it_writes_and_reads_back(self, tmp_path: Path):
        data = {"name": "demo", "items": [1, 2, 3]}
        path = tmp_path / "out.yml"
        yml.dump(data, path)
        assert yml.load(path) == data

    def it_uses_block_style(self, tmp_path: Path):
        path = tmp_path / "out.yml"
        yml.dump({"a": [1, 2]}, path)
        text = path.read_text()
        assert "[1, 2]" not in text
        assert "- 1" in text

    def it_preserves_unicode(self, tmp_path: Path):
        path = tmp_path / "out.yml"
        yml.dump({"author": "Müller"}, path)
        assert "Müller" in path.read_text(encoding="utf-8")


class DescribeYmlLoad:
    def it_returns_none_for_missing_file(self, tmp_path: Path):
        assert yml.load(tmp_path / "nope.yml") is None
