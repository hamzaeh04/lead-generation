"""DecisionMakerService: waterfall across every enabled person_discovery
provider (in registry priority order) to find real decision-makers —
owner, founder, CEO, etc. — at one specific company, given its domain.

Mirrors EmailDiscoveryService's waterfall discipline exactly: the
try/except wraps the `async with ProviderUsageRecorder` block (not the
reverse, so a failure is actually logged as a failure), missing-credentials
vs. all-providers-attempted-and-found-nothing are distinguished, and a
provider returning zero results is not an error — the next provider in
priority order is still tried, since coverage genuinely varies by source.

A company with no domain can't be searched: Apollo's decision-maker lookup
queries by organization domain, not by name — a name-only search would be
far noisier and risks attributing a person to the wrong company of the
same name. (Smartlead has no domain-based lookup at all — it always
raises ProviderUnavailableError here and is silently skipped.)
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.contact import Contact
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.contact_resolver import PersonEntityResolver
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DecisionMakerService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.companies = CompanyRepository(session)
        self.contact_resolver = PersonEntityResolver(ContactRepository(session))
        self.provider_configs = ProviderConfigRepository(session)

    async def find_decision_makers(
        self, *, workspace_id: uuid.UUID, company_id: uuid.UUID, target_titles: list[str]
    ) -> dict:
        company = await self.companies.get_by_id(workspace_id, company_id)
        if company is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
        if not company.domain:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Company has no domain on file — decision-maker search requires one",
            )

        registry_entries = await self.provider_configs.list_enabled_for_category(
            ProviderCategory.PERSON_DISCOVERY
        )
        if not registry_entries:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No person-discovery provider is enabled in the registry",
            )

        missing_credentials: list[str] = []
        for registry_entry in registry_entries:
            provider = provider_factory.build_provider(
                registry_entry.provider, ProviderCategory.PERSON_DISCOVERY, self.settings
            )
            if provider is None:
                missing_credentials.append(registry_entry.provider)
                continue

            candidates = []
            try:
                async with ProviderUsageRecorder(
                    self.session,
                    provider=registry_entry.provider,
                    category=ProviderCategory.PERSON_DISCOVERY,
                    operation="discover_decision_makers",
                    workspace_id=workspace_id,
                ) as usage:
                    candidates = await provider.discover_decision_makers(
                        company.domain, target_titles
                    )
                    usage.records_returned = len(candidates)
            except ProviderUnavailableError as exc:
                logger.warning(
                    "decision_maker_provider_unavailable",
                    provider=registry_entry.provider,
                    error=str(exc),
                )
                continue

            if candidates:
                return await self._persist(workspace_id, company_id, candidates)
            # Ran successfully, found nobody at this domain — a genuine
            # empty result, not a failure. Still worth trying the next
            # enabled provider in case it has coverage this one lacks.

        if registry_entries and len(missing_credentials) == len(registry_entries):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "No enabled person-discovery provider has credentials configured "
                f"(missing: {', '.join(missing_credentials)}).",
            )
        return {"contacts_created": 0, "contacts_matched": 0, "contacts": []}

    async def _persist(
        self, workspace_id: uuid.UUID, company_id: uuid.UUID, candidates: list
    ) -> dict:
        created = matched = 0
        touched: dict[uuid.UUID, Contact] = {}
        for candidate in candidates:
            resolution = await self.contact_resolver.resolve(
                workspace_id=workspace_id, candidate=candidate, company_id=company_id
            )
            touched[resolution.contact.id] = resolution.contact
            if resolution.created:
                created += 1
            else:
                matched += 1

        await self.session.commit()
        # Same reasoning as SearchService: a plain refresh() only covers
        # column attributes, not the `company` relationship ContactRead.
        # company_name reads — a fresh eager-loaded re-query both
        # re-hydrates expired onupdate=func.now() columns and loads
        # `company`, avoiding a MissingGreenlet from touching it unloaded
        # during serialization.
        if touched:
            reloaded = await self.session.execute(
                select(Contact)
                .where(Contact.id.in_(touched.keys()))
                .options(selectinload(Contact.company))
            )
            touched = {c.id: c for c in reloaded.scalars().all()}

        logger.info(
            "decision_makers_found",
            company_id=str(company_id),
            created=created,
            matched=matched,
        )
        return {
            "contacts_created": created,
            "contacts_matched": matched,
            "contacts": list(touched.values()),
        }
