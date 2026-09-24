"""Ties together: provider registry check -> provider instantiation ->
discovery call -> normalization/dedup (via the Phase 2 resolvers) -> persist.

This is a single explicit provider call (the caller picks exactly one
enabled provider and category), not a cross-provider waterfall — the
NL-search UI flow (section 60) has the user choose a provider as a
distinct step. Every call is logged via ProviderUsageRecorder for cost
tracking and provider health (Phase 6).
"""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.company import Company
from app.models.contact import Contact
from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    NormalizedContact,
    ProviderCategory,
    ProviderUnavailableError,
)
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.repositories.search_batch_repository import SearchBatchRepository
from app.services import provider_factory
from app.services.company_resolver import CompanyEntityResolver
from app.services.contact_resolver import PersonEntityResolver
from app.services.lead_qualification_service import LeadQualificationService
from app.services.lead_reveal_service import _AUTO_REVEAL_PROVIDERS, LeadRevealService
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DISCOVERY_CATEGORIES = {
    ProviderCategory.COMPANY_DISCOVERY,
    ProviderCategory.PERSON_DISCOVERY,
}


class SearchService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.provider_configs = ProviderConfigRepository(session)
        self.company_resolver = CompanyEntityResolver(CompanyRepository(session))
        self.contact_resolver = PersonEntityResolver(ContactRepository(session))
        self.search_batches = SearchBatchRepository(session)

    async def execute(
        self,
        *,
        workspace_id: uuid.UUID,
        provider_name: str,
        category: ProviderCategory,
        criteria: DiscoveryCriteria,
        created_by: uuid.UUID | None = None,
    ) -> dict:
        if category not in _DISCOVERY_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{category}' does not support discovery search",
            )

        registry_entry = await self.provider_configs.get_by_provider_and_category(
            provider_name, category
        )
        if registry_entry is None or not registry_entry.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider_name}' is not enabled for category '{category}'. "
                    "An admin must enable it via PATCH /api/v1/providers/{id}."
                ),
            )

        provider = await provider_factory.build_provider_for_workspace(
            self.session, workspace_id, provider_name, category, self.settings
        )
        if provider is None:
            env_var = provider_factory.required_env_var(provider_name, category)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Provider '{provider_name}' credentials not configured "
                    f"(save in Settings → Provider API keys, or set {env_var})."
                ),
            )

        contacts_found: list[NormalizedContact] = []
        companies_found: list[NormalizedCompany] = []
        operation = {
            ProviderCategory.COMPANY_DISCOVERY: "discover_companies",
            ProviderCategory.PERSON_DISCOVERY: "discover_people",
        }[category]

        async with ProviderUsageRecorder(
            self.session,
            provider=provider_name,
            category=category,
            operation=operation,
            workspace_id=workspace_id,
        ) as usage:
            try:
                if category == ProviderCategory.COMPANY_DISCOVERY:
                    companies_found = await provider.discover_companies(criteria)
                else:  # PERSON_DISCOVERY
                    contacts_found = await provider.discover_people(criteria)
            except ProviderUnavailableError as exc:
                logger.warning("search_provider_unavailable", provider=provider_name, error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Provider request failed: {exc}",
                ) from exc
            finally:
                usage.records_returned = len(companies_found) + len(contacts_found)

        companies_created = companies_matched = 0
        touched_companies: dict[uuid.UUID, Company] = {}

        for candidate in companies_found:
            resolution = await self.company_resolver.resolve(
                workspace_id=workspace_id, candidate=candidate
            )
            touched_companies[resolution.company.id] = resolution.company
            if resolution.created:
                companies_created += 1
            else:
                companies_matched += 1

        contacts_created = contacts_matched = 0
        touched_contacts: dict[uuid.UUID, Contact] = {}
        contact_is_new: dict[uuid.UUID, bool] = {}

        for contact_candidate in contacts_found:
            company_id = await self._resolve_company_for_contact(workspace_id, contact_candidate)
            resolution = await self.contact_resolver.resolve(
                workspace_id=workspace_id, candidate=contact_candidate, company_id=company_id
            )
            touched_contacts[resolution.contact.id] = resolution.contact
            contact_is_new[resolution.contact.id] = resolution.created
            if resolution.created:
                contacts_created += 1
            else:
                contacts_matched += 1

        batch = None
        if touched_companies or touched_contacts:
            batch = await self.search_batches.create(
                workspace_id=workspace_id,
                provider=provider_name,
                category=category,
                criteria_snapshot=asdict(criteria),
                created_by=created_by,
            )
            batch.companies_created = companies_created
            batch.companies_matched = companies_matched
            batch.contacts_created = contacts_created
            batch.contacts_matched = contacts_matched
            for contact_id in touched_contacts:
                self.search_batches.add_contact(
                    batch=batch, contact_id=contact_id, is_new=contact_is_new[contact_id]
                )

        await self.session.commit()
        if batch is not None:
            await self.session.refresh(batch)
        # Matched (not newly-created) records were mutated in-place, and
        # onupdate=func.now() columns are expired after commit — refresh
        # before returning them for (sync) Pydantic serialization.
        for company in touched_companies.values():
            await self.session.refresh(company)
        if touched_contacts:
            # A plain refresh() only covers column attributes, not the
            # `company`/`sources` relationships ContactRead.company_name
            # and .revealable read — a fresh eager-loaded re-query both
            # re-hydrates expired columns and loads both relationships in
            # one pass, avoiding a MissingGreenlet from an unloaded
            # relationship touched during serialization.
            reloaded = await self.session.execute(
                select(Contact)
                .where(Contact.id.in_(touched_contacts.keys()))
                .options(selectinload(Contact.company), selectinload(Contact.sources), selectinload(Contact.qualifications))
            )
            touched_contacts = {c.id: c for c in reloaded.scalars().all()}

        if touched_contacts and provider_name in _AUTO_REVEAL_PROVIDERS:
            # Reveal masked results automatically — no manual "Reveal"
            # button anymore, per explicit instruction. Runs before
            # qualification so the AI scoring step sees real email/
            # location/seniority data instead of the pre-reveal masked
            # state. reveal_many reuses reveal()'s own guards (already
            # has email, already attempted) so this never re-bills a
            # contact across repeated searches.
            reveal_service = LeadRevealService(self.session, self.settings)
            await reveal_service.reveal_many(
                workspace_id=workspace_id, contacts=list(touched_contacts.values()), provider=provider_name
            )
            reloaded = await self.session.execute(
                select(Contact)
                .where(Contact.id.in_(touched_contacts.keys()))
                .options(selectinload(Contact.company), selectinload(Contact.sources), selectinload(Contact.qualifications))
                .execution_options(populate_existing=True)
            )
            touched_contacts = {c.id: c for c in reloaded.scalars().all()}

        qualification_result = None
        if touched_contacts:
            # Score every lead this search touched immediately, rather than
            # leaving it to a separate manual step — paced (see
            # LeadQualificationService._BATCH_PACING_SECONDS) to stay under
            # the AI provider's burst rate limit. This is why a person
            # search now takes noticeably longer than before: it's no
            # longer just the provider call, it's provider call + one AI
            # qualification per new lead.
            qualification_service = LeadQualificationService(self.session, self.settings)
            qualification_result = await qualification_service.qualify_many(
                workspace_id=workspace_id, contacts=list(touched_contacts.values())
            )
            # qualify_many committed its own rows per-contact; re-fetch so
            # the response reflects each contact's just-written qualification
            # instead of the pre-scoring snapshot taken above. populate_existing
            # is required here: these Contact objects are already identity-mapped
            # in this same session with `qualifications` already loaded (as
            # empty, from the reload above) — without it, SQLAlchemy trusts
            # that already-loaded state and silently keeps serving the stale
            # empty list instead of re-querying it.
            reloaded = await self.session.execute(
                select(Contact)
                .where(Contact.id.in_(touched_contacts.keys()))
                .options(selectinload(Contact.company), selectinload(Contact.sources), selectinload(Contact.qualifications))
                .execution_options(populate_existing=True)
            )
            touched_contacts = {c.id: c for c in reloaded.scalars().all()}

        logger.info(
            "search_executed",
            provider=provider_name,
            category=str(category),
            batch_id=str(batch.id) if batch is not None else None,
            companies_created=companies_created,
            companies_matched=companies_matched,
            contacts_created=contacts_created,
            contacts_matched=contacts_matched,
            leads_qualified=qualification_result.qualified if qualification_result else 0,
            leads_qualify_failed=qualification_result.failed if qualification_result else 0,
        )

        return {
            "batch_id": batch.id if batch is not None else None,
            "companies_created": companies_created,
            "companies_matched": companies_matched,
            "contacts_created": contacts_created,
            "contacts_matched": contacts_matched,
            "companies": list(touched_companies.values()),
            "contacts": list(touched_contacts.values()),
        }

    async def _resolve_company_for_contact(
        self, workspace_id: uuid.UUID, contact: NormalizedContact
    ) -> uuid.UUID | None:
        """A person-search result often carries its employer's name/domain —
        resolve that into a Company too so the contact links to it, rather
        than leaving company_id null when we actually have the data."""
        if not contact.company_domain and not contact.company_name:
            return None

        company_candidate = NormalizedCompany(
            metadata=contact.metadata,
            name=contact.company_name,
            domain=contact.company_domain,
        )
        resolution = await self.company_resolver.resolve(
            workspace_id=workspace_id, candidate=company_candidate
        )
        return resolution.company.id
