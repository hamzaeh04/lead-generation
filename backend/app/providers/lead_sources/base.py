"""Company discovery provider interface."""
from __future__ import annotations

from abc import abstractmethod

from app.providers.base import BaseProvider, DiscoveryCriteria, NormalizedCompany


class CompanyDiscoveryProvider(BaseProvider):
    """Finds companies matching structured ICP criteria (e.g. Apollo org search)."""

    @abstractmethod
    async def discover_companies(
        self, criteria: DiscoveryCriteria
    ) -> list[NormalizedCompany]:
        """Return companies matching criteria. Never fabricates results —
        an empty list means the provider found nothing, not an error."""
        raise NotImplementedError
