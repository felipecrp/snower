"""Tests for user configuration storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from snow.user_config import RecentProject, load_recent_projects, remember_recent_project, remove_recent_project


class DescribeLoadRecentProjects:
    def it_returns_empty_when_file_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", tmp_path / "nonexistent.yaml")
        assert load_recent_projects() == []

    def it_returns_empty_when_file_is_empty(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text("")
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)
        assert load_recent_projects() == []

    def it_silently_drops_entries_with_missing_project(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(
            "- path: /nonexistent/project\n"
            "  name: Dead\n"
            "- path: /another/dead\n"
            "  name: AlsoDead\n"
        )
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)
        assert load_recent_projects() == []

    def it_keeps_valid_entries(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        valid_path = tmp_path / "valid_project"
        valid_path.mkdir()
        (valid_path / "project.yml").touch()

        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(
            f"- path: {valid_path}\n"
            "  name: ValidProject\n"
            "  description: A good project\n"
        )
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)
        recents = load_recent_projects()
        assert len(recents) == 1
        assert recents[0].path == str(valid_path)
        assert recents[0].name == "ValidProject"
        assert recents[0].description == "A good project"


class DescribeRememberRecentProject:
    def it_adds_new_entry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        yaml_file = tmp_path / "recent.yaml"
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)

        proj = tmp_path / "project1"
        proj.mkdir()
        (proj / "project.yml").touch()

        entry = RecentProject(path=str(proj), name="Project1")
        result = remember_recent_project(entry)

        assert len(result) == 1
        assert result[0].path == str(proj)
        assert yaml_file.exists()

    def it_deduplicates_by_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        proj = tmp_path / "project1"
        proj.mkdir()
        (proj / "project.yml").touch()

        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(f"- path: {proj}\n  name: Old\n")
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)

        entry = RecentProject(path=str(proj), name="Updated", description="New desc")
        result = remember_recent_project(entry)

        assert len(result) == 1
        assert result[0].name == "Updated"
        assert result[0].description == "New desc"

    def it_prepends_new_entries(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        p1 = tmp_path / "old"
        p1.mkdir()
        (p1 / "project.yml").touch()

        p2 = tmp_path / "new"
        p2.mkdir()
        (p2 / "project.yml").touch()

        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(f"- path: {p1}\n  name: Old\n")
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)

        entry = RecentProject(path=str(p2), name="New")
        result = remember_recent_project(entry)

        assert len(result) == 2
        assert result[0].path == str(p2)
        assert result[1].path == str(p1)

    def it_caps_at_five(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        paths = []
        for i in range(1, 6):
            p = tmp_path / f"p{i}"
            p.mkdir()
            (p / "project.yml").touch()
            paths.append(str(p))

        yaml_lines = "\n".join(f"- path: {p}\n  name: P{i}" for i, p in enumerate(paths, 1))
        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(yaml_lines)
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)

        p6 = tmp_path / "p6"
        p6.mkdir()
        (p6 / "project.yml").touch()

        entry = RecentProject(path=str(p6), name="P6")
        result = remember_recent_project(entry)

        assert len(result) == 5
        assert result[0].path == str(p6)
        assert result[4].path == paths[3]  # p4


class DescribeRemoveRecentProject:
    def it_removes_by_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        p1 = tmp_path / "p1"
        p1.mkdir()
        (p1 / "project.yml").touch()

        p2 = tmp_path / "p2"
        p2.mkdir()
        (p2 / "project.yml").touch()

        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(f"- path: {p1}\n  name: P1\n- path: {p2}\n  name: P2\n")
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)

        result = remove_recent_project(str(p1))

        assert len(result) == 1
        assert result[0].path == str(p2)

    def it_returns_empty_when_last_removed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        p1 = tmp_path / "p1"
        p1.mkdir()
        (p1 / "project.yml").touch()

        yaml_file = tmp_path / "recent.yaml"
        yaml_file.write_text(f"- path: {p1}\n  name: P1\n")
        monkeypatch.setattr("snow.user_config.RECENT_PROJECTS_PATH", yaml_file)

        result = remove_recent_project(str(p1))

        assert result == []
