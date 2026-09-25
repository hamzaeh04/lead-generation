"""Manual, on-demand Apollo phone-number enrichment.

Deliberately separate from LeadRevealService's automatic reveal-on-search
flow: phone reveal costs extra Apollo credits (8 per mobile number found)
and is delivered asynchronously via webhook, so it's never triggered
automatically — only by an explicit "Enrich phones" click (see
POST /search-batches/{id}/enrich-phones). The phone number itself isn't
available when this returns; it lands later via the webhook handler in
app/api/v1/webhooks.py, once Apollo's lookup completes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.contact import Contact
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.repositories.contact_repository import ContactRepository
from app.services import provider_factory
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PHONE_ENRICHABLE_PROVIDERS = ("apollo",)


@dataclass(frozen=True, slots=True)
class PhoneRequestResult:
    requested: int
    skipped: int
    failed: int
    total: int


class PhoneEnrichmentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.contacts = ContactRepository(session)

    async def request_many(
        self, *, workspace_id: uuid.UUID, contacts: list[Contact], provider: str, webhook_url: str
    ) -> PhoneRequestResult:
        if provider not in _PHONE_ENRICHABLE_PROVIDERS:
            raise ProviderUnavailableError(f"{provider}: phone enrichment is not supported")

        built_provider = await provider_factory.build_provider_for_workspace(
            self.session, workspace_id, provider, ProviderCategory.PERSON_DISCOVERY, self.settings
        )
        if built_provider is None:
            env_var = provider_factory.required_env_var(provider, ProviderCategory.PERSON_DISCOVERY)
            raise ProviderUnavailableError(f"{provider}: credentials not configured (set {env_var})")

        requested = skipped = failed = 0
        for contact in contacts:
            # contact.sources is already eager-loaded by the caller
            # (SearchBatchRepository.list_contacts) — reusing it here
            # instead of a fresh get_source() query, and committing only
            # once after the whole loop (not per-contact) rather than
            # flushing per-contact, is deliberate: a mid-loop commit()
            # expires every object in the session's identity map,
            # including the *other* not-yet-processed contacts in this
            # same pre-loaded list, and the next iteration's plain
            # attribute reads (contact.phone, contact.sources) on an
            # expired object then trigger a synchronous lazy-load that
            # blows up with MissingGreenlet outside of an awaited call.
            source = next((s for s in contact.sources if s.provider == provider), None)
            if source is None:
                continue  # not this call's job — same convention as LeadRevealService.reveal_many
            if contact.phone or contact.phone_reveal_attempted or not source.external_id:
                skipped += 1
                continue

            try:
                await built_provider.request_phone_reveal(
                    source.external_id, webhook_url=webhook_url
                )
                contact.phone_reveal_attempted = True
                await self.session.flush()
                requested += 1
                logger.info("phone_reveal_requested", contact_id=str(contact.id), provider=provider)
            except ProviderUnavailableError as exc:
                logger.warning(
                    "phone_reveal_request_failed", contact_id=str(contact.id), error=str(exc)
                )
                failed += 1

        await self.session.commit()
        return PhoneRequestResult(
            requested=requested, skipped=skipped, failed=failed, total=len(contacts)
        )
