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

    async def reveal(self, external_id: str, *, raw_reference: dict | None = None) -> dict | None:
        """Enriches a masked search result (Apollo, Smartlead) into real
        contact details — email, phone, full name. `raw_reference` is the
        ContactSource's stored raw payload from the original search hit;
        Smartlead's unlock call needs the `filter_id` that was captured in
        there (see smartlead_provider.py), Apollo ignores it. Not every
        provider supports this, so it isn't abstract: the default signals
        "not supported" via the same ProviderUnavailableError convention
        used throughout this codebase, letting callers treat it as a
        normal skip rather than a crash. Returns None (not an error) when
        the provider supports reveal but found nothing for this id."""
        raise ProviderUnavailableError(f"{self.name}: reveal is not supported by this provider")

    async def request_phone_reveal(self, external_id: str, *, webhook_url: str) -> None:
        """Kicks off an async phone-number reveal for an already-revealed
        contact (Apollo only, so far) — the phone itself is NOT returned
        by this call; the provider delivers it later via a POST to
        `webhook_url`. Manual/on-demand only, never part of the automatic
        reveal-on-search flow, since phone reveal costs extra credits.
        Same "not supported" convention as reveal()."""
        raise ProviderUnavailableError(f"{self.name}: phone reveal is not supported by this provider")
