"""Tests for the provider factory."""

from __future__ import annotations

from snow.domain.models import Project, ProviderConfig
from snow.providers.factory import get_provider
from snow.providers.openalex_provider import OpenAlexProvider
from snow.providers.scholarly_provider import ScholarlyProvider
from snow.providers.semantic_scholar_provider import SemanticScholarProvider


class DescribeGetProvider:
    def it_returns_openalex_by_default_when_no_providers_configured(self):
        project = Project(name="empty")
        assert isinstance(get_provider(project), OpenAlexProvider)

    def it_uses_researcher_email_for_openalex(self):
        project = Project(name="p")
        provider = get_provider(project, email="me@example.com")
        assert isinstance(provider, OpenAlexProvider)
        assert provider._email == "me@example.com"

    def it_skips_disabled_providers(self):
        project = Project(
            name="p",
            providers=[
                ProviderConfig(name="scholarly", enabled=False),
                ProviderConfig(name="openalex", enabled=True),
            ],
        )
        provider = get_provider(project, email="me@example.com")
        assert isinstance(provider, OpenAlexProvider)
        assert provider._email == "me@example.com"

    def it_picks_first_enabled_provider(self):
        project = Project(
            name="p",
            providers=[
                ProviderConfig(name="semantic_scholar", enabled=True),
                ProviderConfig(name="openalex", enabled=True),
            ],
        )
        assert isinstance(get_provider(project), SemanticScholarProvider)

    def it_resolves_scholarly_provider(self):
        project = Project(name="p", providers=[ProviderConfig(name="scholarly", enabled=True)])
        assert isinstance(get_provider(project), ScholarlyProvider)
