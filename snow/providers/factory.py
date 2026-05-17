"""Resolve the active provider from project configuration."""

from __future__ import annotations

from snow.domain.models import Project
from snow.providers.base import Provider
from snow.providers.openalex_provider import OpenAlexProvider
from snow.providers.scholarly_provider import ScholarlyProvider
from snow.providers.semantic_scholar_provider import SemanticScholarProvider


def get_provider(project: Project, email: str | None = None) -> Provider:
    for cfg in project.providers:
        if not cfg.enabled:
            continue
        if cfg.name == "scholarly":
            return ScholarlyProvider()
        if cfg.name == "semantic_scholar":
            return SemanticScholarProvider(api_key=cfg.options.get("api_key") or None)
        if cfg.name == "openalex":
            return OpenAlexProvider(email=email or cfg.options.get("email") or None)
    return OpenAlexProvider(email=email)


def get_enrichment_provider(project: Project, email: str | None = None) -> Provider:
    """Always OpenAlex — used at import time to fill missing fields like abstract."""
    return OpenAlexProvider(email=email)
