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
from app.models.contact import Contact
from app.providers.base import ProviderCategory, ProviderUnavailableError
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

    async def reveal(self, *, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> tuple[Contact, bool]:
        """Returns (contact, revealed). revealed=False means the provider
        was called but had nothing new to reveal — a normal outcome, not
        an error, same convention used everywhere else in this app."""
        contact = await self.contacts.get_by_id(workspace_id, contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

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

        if revealed is None:
            return contact, False

        if revealed.get("email"):
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

        await self.session.commit()
        # A plain refresh() only covers column attributes, not the
        # `company`/`sources` relationships ContactRead.company_name and
        # .revealable read — re-fetch eager-loaded (see ContactRepository.
        # get_by_id) to avoid a MissingGreenlet from an unloaded
        # relationship touched during serialization.
        refreshed = await self.contacts.get_by_id(workspace_id, contact.id)
        assert refreshed is not None  # just committed/refreshed this exact row
        logger.info("lead_revealed", contact_id=str(contact.id), provider=source.provider)
        return refreshed, True
