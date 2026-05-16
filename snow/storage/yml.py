"""YAML reader/writer tuned for git-friendly output.

Writes use block style and a stable indent so diffs stay readable and
minimal across edits.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def _make_yaml() -> YAML:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 100
    yaml.allow_unicode = True
    return yaml


def load(path: Path) -> Any:
    if not path.exists():
        return None
    yaml = _make_yaml()
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def dump(data: Any, path: Path) -> None:
    yaml = _make_yaml()
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    path.write_text(buffer.getvalue(), encoding="utf-8")
