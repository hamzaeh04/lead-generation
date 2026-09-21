"""Person / decision-maker discovery provider interfaces."""
from __future__ import annotations

from abc import abstractmethod

from app.providers.base import BaseProvider, DiscoveryCriteria, NormalizedContact, ProviderUnavailableError


class PersonDiscoveryProvider(BaseProvider):
    """Finds people matching structured criteria (title, seniority, company, ...)."""

    @abstractmethod
    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        raise NotImplementedError

    @abstractmethod
    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        """Company -> decision-makers lookup (e.g. Apollo org employees filtered by title)."""
        raise NotImplementedError

    async def reveal(self, external_id: str) -> dict | None:
        """Enriches a masked search result (e.g. Apollo's) into real contact
        details — email, phone, full name. Not every provider masks its
        search results (Smartlead's SmartProspect returns real data
        directly), so this isn't abstract: the default signals "not
        supported" via the same ProviderUnavailableError convention used
        throughout this codebase, letting callers treat it as a normal
        skip rather than a crash. Returns None (not an error) when the
        provider supports reveal but found nothing for this id."""
        raise ProviderUnavailableError(f"{self.name}: reveal is not supported by this provider")
