"""Reveals a masked search result's real contact details on demand.

Apollo's people-search returns masked data (see apollo_provider.py) — this
service is the explicit, per-lead action that spends an Apollo credit to
get the real email/phone/name, rather than that happening automatically
for every search result. Not every provider supports/needs this (see
PersonDiscoveryProvider.reveal's default "not supported" behavior).
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.company import Company
from app.models.contact import Contact
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.services import provider_factory
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Only providers whose search step can mask results need a reveal call.
_REVEALABLE_PROVIDERS = ("apollo",)


class LeadRevealService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.contacts = ContactRepository(session)
        self.companies = CompanyRepository(session)

    async def reveal(self, *, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> tuple[Contact, bool]:
        """Returns (contact, revealed). revealed=False means the provider
        was called but had nothing new to reveal — a normal outcome, not
        an error, same convention used everywhere else in this app.

        Apollo's /people/match has no server-side memory of "already
        tried" — calling it again for the same person spends another
        credit for the identical non-result. So this method itself (not
        just the UI) refuses a second attempt once one has already come
        back with no email, via email_reveal_attempted."""
        contact = await self.contacts.get_by_id(workspace_id, contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

        if contact.email:
            return contact, False

        if contact.email_reveal_attempted:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Reveal was already attempted for this lead and found no email — "
                "retrying would spend another credit for the same result.",
            )

        source = None
        for provider_name in _REVEALABLE_PROVIDERS:
            source = await self.contacts.get_source(contact.id, provider_name)
            if source is not None:
                break
        if source is None or not source.external_id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "This lead has no source that supports revealing details"
            )

        provider = provider_factory.build_provider(
            source.provider, ProviderCategory.PERSON_DISCOVERY, self.settings
        )
        if provider is None:
            env_var = provider_factory.required_env_var(source.provider, ProviderCategory.PERSON_DISCOVERY)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"Provider '{source.provider}' credentials not configured (set {env_var}).",
            )

        try:
            async with ProviderUsageRecorder(
                self.session,
                provider=source.provider,
                category=ProviderCategory.PERSON_DISCOVERY,
                operation="reveal",
                workspace_id=workspace_id,
            ) as usage:
                revealed = await provider.reveal(source.external_id)
                usage.records_returned = 1 if revealed else 0
        except ProviderUnavailableError as exc:
            logger.warning("lead_reveal_provider_unavailable", provider=source.provider, error=str(exc))
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Reveal failed: {exc}") from exc

        contact.email_reveal_attempted = True

        if revealed is None:
            await self.session.commit()
            # Same MissingGreenlet hazard as the success path below —
            # returning the stale `contact` directly would try to lazy-load
            # an expired column outside a greenlet during serialization.
            refreshed = await self.contacts.get_by_id(workspace_id, contact.id)
            assert refreshed is not None
            return refreshed, False

        email_found = bool(revealed.get("email"))
        if email_found:
            contact.email = revealed["email"]
            contact.field_provenance = {
                **contact.field_provenance,
                "email": {"provider": source.provider, "revealed": True},
            }
        if revealed.get("phone"):
            contact.phone = revealed["phone"]
        if revealed.get("last_name") and not contact.last_name:
            contact.last_name = revealed["last_name"]
        if revealed.get("full_name"):
            contact.full_name = revealed["full_name"]
        if revealed.get("email_status"):
            contact.email_status = revealed["email_status"]
        if revealed.get("linkedin_url") and not contact.linkedin_url:
            contact.linkedin_url = revealed["linkedin_url"]
        if revealed.get("city") and not contact.city:
            contact.city = revealed["city"]
        if revealed.get("state") and not contact.state:
            contact.state = revealed["state"]
        if revealed.get("country") and not contact.country:
            contact.country = revealed["country"]
        if revealed.get("seniority") and not contact.seniority:
            contact.seniority = revealed["seniority"]
        if revealed.get("department") and not contact.department:
            contact.department = revealed["department"]

        org = revealed.get("organization")
        if org and contact.company_id:
            company = await self.companies.get_by_id(workspace_id, contact.company_id)
            if company is not None:
                self._fill_company_fields(company, org)

        await self.session.commit()
        # A plain refresh() only covers column attributes, not the
        # `company`/`sources` relationships ContactRead.company_name and
        # .revealable read — re-fetch eager-loaded (see ContactRepository.
        # get_by_id) to avoid a MissingGreenlet from an unloaded
        # relationship touched during serialization.
        refreshed = await self.contacts.get_by_id(workspace_id, contact.id)
        assert refreshed is not None  # just committed/refreshed this exact row
        logger.info(
            "lead_revealed", contact_id=str(contact.id), provider=source.provider, email_found=email_found
        )
        # "revealed" specifically means an email was obtained — that's the
        # whole point of clicking this button. Apollo returning a bare
        # last_name/phone with no email is not the success the UI's
        # "Details revealed" message implies.
        return refreshed, email_found

    @staticmethod
    def _fill_company_fields(company: Company, org: dict) -> None:
        """Only fills currently-empty fields — never overwrites a value
        this workspace already has from another source (e.g. an earlier
        search), matching the same "don't clobber existing data"
        convention used for contact fields above."""
        field_map = {
            "industry": org.get("industry"),
            "employee_count": org.get("employee_count"),
            "annual_revenue": org.get("annual_revenue"),
            "founded_year": org.get("founded_year"),
            "website": org.get("website"),
            "phone": org.get("phone"),
            "linkedin_url": org.get("linkedin_url"),
            "city": org.get("city"),
            "state": org.get("state"),
            "country": org.get("country"),
        }
        for field_name, value in field_map.items():
            if value is not None and getattr(company, field_name) is None:
                setattr(company, field_name, value)
