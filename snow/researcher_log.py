"""Per-researcher file logger factory."""

from __future__ import annotations

import logging
from pathlib import Path


def get_researcher_logger(project_root: Path, researcher_id: str) -> logging.Logger:
    safe = researcher_id.replace("@", "_at_").replace(".", "_")
    name = f"snow.researcher.{safe}"
    log = logging.getLogger(name)
    if not log.handlers:
        log_dir = project_root / "researcher"
        log_dir.mkdir(parents=True, exist_ok=True)
        h = logging.FileHandler(log_dir / f"{researcher_id}.log", encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s — %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log
