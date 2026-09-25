"""AI personalization: builds a strictly-grounded prompt from a contact's
known, real data — never anything invented — and asks an AIProvider to
draft an outreach email. Waterfall across enabled `ai`-category providers,
same pattern as email discovery/verification (Phase 6).

Grounding rule (section 37): only facts explicitly present on the
Contact/Company/latest IntentSignal are ever placed in `source_fields`. No
placeholder or inferred values are added. The system prompt instructs the
model never to invent awards, customers, revenue, funding, or partnerships,
and to fall back to generic-but-truthful copy when a fact is missing — but
that instruction cannot *guarantee* the model complies; it only reduces the
odds, same as with any LLM. `source_fields_used` on the stored record is
the audit trail of what was actually offered as grounding.
"""
from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.ai_generation import AIGeneration
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.providers.ai.base import AIGenerationRequest
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.repositories.ai_generation_repository import AIGenerationRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.intent_signal_repository import IntentSignalRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.services.web_enrichment_service import scrape_company_website
from app.utils.logging import get_logger

logger = get_logger(__name__)

PROMPT_VERSION = "v2"

# Who we are pitching as — kept explicit so the model never invents our offer.
_SELLER_CONTEXT: dict[str, str] = {
    "our_company_name": "NextApps",
    "our_services": (
        "custom web applications and mobile applications "
        "(design, build, and ongoing product engineering)"
    ),
    "our_offer": (
        "NextApps helps organizations ship and scale reliable web apps and "
        "mobile apps — from MVPs to production platforms — with clear delivery "
        "and modern product engineering."
    ),
}

_INSTRUCTIONS = (
    "You are drafting a short, truthful cold outreach email from NextApps. "
    "Our only offer is custom web application and mobile application development "
    "services (see our_company_name, our_services, and our_offer in the JSON). "
    "The email must clearly pitch those services and invite a short conversation "
    "about a possible web/mobile project or product build. "
    "Personalize using ONLY the prospect facts in the JSON — never invent or "
    "assume any fact about the prospect not explicitly listed (no fabricated "
    "awards, customers, revenue, funding, projects, or partnerships). "
    "If a company_website_excerpt field is present, it is real text scraped "
    "from the company's own site — you may reference it the same as any other "
    "listed fact, but still never state anything beyond what it or the other "
    "fields actually say. "
    "Connect their real context (role, company, location, public excerpt) to "
    "why a modern web or mobile app partnership with NextApps could help — "
    "without inventing their needs. If facts are limited, keep personalization "
    "light and still pitch NextApps web/mobile services truthfully. "
    "Tone: professional, concise, human — not salesy hype. "
    "Respond with a JSON object with exactly these string keys: "
    '"subject", "opening_line", "body", "cta", "outreach_angle". '
    "body should be the full email body (greeting through soft close) and "
    "must mention NextApps and web/mobile application services."
)


class PersonalizationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.contacts = ContactRepository(session)
        self.companies = CompanyRepository(session)
        self.intent_signals = IntentSignalRepository(session)
        self.provider_configs = ProviderConfigRepository(session)
        self.generations = AIGenerationRepository(session)

    async def personalize(
        self, *, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> AIGeneration:
        contact = await self.contacts.get_by_id(workspace_id, contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")

        company = None
        if contact.company_id is not None:
            company = await self.companies.get_by_id(workspace_id, contact.company_id)

        latest_signal = None
        if company is not None:
            signals = await self.intent_signals.list_for_company(workspace_id, company.id)
            latest_signal = signals[0] if signals else None  # already ordered newest-first

        website_excerpt = None
        if company is not None and (company.domain or company.website):
            # Best-effort — a failed/timed-out scrape just means this run
            # falls back to DB-only facts, same never-fabricate convention
            # as everywhere else (see web_enrichment_service's docstring).
            website_excerpt = await scrape_company_website(domain=company.domain, website=company.website)

        source_fields = self._build_source_fields(contact, company, latest_signal, website_excerpt)

        registry_entries = await self.provider_configs.list_enabled_for_category(
            ProviderCategory.AI
        )
        if not registry_entries:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "No AI provider is enabled in the registry"
            )

        missing_credentials: list[str] = []
        last_error: str | None = None
        for registry_entry in registry_entries:
            provider = await provider_factory.build_provider_for_workspace(
                self.session, workspace_id, registry_entry.provider, ProviderCategory.AI, self.settings
            )
            if provider is None:
                missing_credentials.append(registry_entry.provider)
                continue

            try:
                async with ProviderUsageRecorder(
                    self.session,
                    provider=registry_entry.provider,
                    category=ProviderCategory.AI,
                    operation="generate",
                    workspace_id=workspace_id,
                ) as usage:
                    result = await provider.generate(
                        AIGenerationRequest(
                            prompt_version=PROMPT_VERSION,
                            instructions=_INSTRUCTIONS,
                            source_fields=source_fields,
                        )
                    )
                    parsed = self._parse_result_text(result.text)
                    usage.records_returned = 1
            except ProviderUnavailableError as exc:
                logger.warning(
                    "personalization_provider_unavailable",
                    provider=registry_entry.provider,
                    error=str(exc),
                )
                last_error = str(exc)
                continue

            generation = self.generations.create(
                workspace_id=workspace_id,
                contact_id=contact.id,
                provider=registry_entry.provider,
                model=result.model,
                prompt_version=result.prompt_version,
                source_fields_used=result.source_fields_used,
                subject=parsed.get("subject"),
                opening_line=parsed.get("opening_line"),
                body=parsed.get("body"),
                cta=parsed.get("cta"),
                outreach_angle=parsed.get("outreach_angle"),
                personalization_source="intent_signal" if latest_signal else None,
                signal_id=latest_signal.id if latest_signal else None,
                source_url=latest_signal.source_url if latest_signal else None,
                raw_response={"text": result.text},
            )
            await self.session.commit()
            await self.session.refresh(generation)

            logger.info(
                "ai_personalization_generated",
                contact_id=str(contact.id),
                provider=registry_entry.provider,
                source_fields_used=result.source_fields_used,
            )
            return generation

        if len(missing_credentials) == len(registry_entries):
            # Every enabled provider was skipped for missing credentials —
            # nothing was actually attempted, so this is a config problem.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"No enabled AI provider has credentials configured (missing: {', '.join(missing_credentials)}).",
            )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"All enabled AI providers failed. Last error: {last_error}",
        )

    def _build_source_fields(
        self,
        contact: Contact,
        company: Company | None,
        signal: IntentSignal | None,
        website_excerpt: str | None = None,
    ) -> dict[str, str]:
        fields: dict[str, str] = {}
        fields.update(_SELLER_CONTEXT)
        if contact.full_name:
            fields["contact_full_name"] = contact.full_name
        if contact.job_title:
            fields["contact_job_title"] = contact.job_title
        if company:
            if company.name:
                fields["company_name"] = company.name
            if company.industry:
                fields["company_industry"] = company.industry
            if company.city:
                fields["company_city"] = company.city
            if company.state:
                fields["company_state"] = company.state
            if company.website:
                fields["company_website"] = company.website
        if website_excerpt:
            fields["company_website_excerpt"] = website_excerpt
        if signal and signal.signal_text:
            fields["recent_intent_signal"] = signal.signal_text
            fields["recent_intent_signal_source"] = signal.source_url
        return fields

    def _parse_result_text(self, text: str) -> dict[str, str]:
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise ProviderUnavailableError(f"AI response was not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ProviderUnavailableError("AI response JSON was not an object")
        return parsed
