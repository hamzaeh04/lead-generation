"""Translates a natural-language prospecting prompt into structured search
criteria for a specific provider.

Neither Apollo's nor Smartlead's real search APIs accept free-text prompts
— both require structured filters (job titles, seniority, company size,
location, etc; see the provider files for each one's exact schema).
Smartlead's own "Ask AI to build your prospect list" feature in their web
app works the same way: it's their frontend translating your sentence into
those filters before calling their real, filter-only API. This service
does the same translation via Groq, the AI provider already used for
personalization elsewhere in this codebase.

Grounding rule: the model is only asked to extract what the prompt actually
says. It must never invent a filter value the prompt didn't mention —
mirrors PersonalizationService's no-fabrication instruction. A field the
prompt is silent on stays absent from the result, not guessed.
"""
from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.providers.ai.base import AIGenerationRequest
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)

PROMPT_VERSION = "v1"

# Field vocabularies the model may use, one per provider. Anything the
# caller receives outside DiscoveryCriteria's own named fields (keywords,
# industry, country, state, city, company_name, domain,
# employee_count_min/max, job_titles, seniorities) is treated as a
# provider-specific extra_filters entry — see search.py's /parse-prompt.
_SCHEMA_DESCRIPTIONS: dict[str, str] = {
    "apollo": (
        "job_titles (list of strings), seniorities (list, only from: owner, "
        "founder, c_suite, partner, vp, head, director, manager, senior, "
        "entry, intern), city, state, country, domain (a specific company "
        "website domain if one is named), keywords (free text), "
        "employee_count_min, employee_count_max (integers), "
        "technologies (list of strings, software/tools the target companies "
        "use), email_status (list, only from: verified, unverified, "
        "\"likely to engage\", unavailable), revenue_min, revenue_max "
        "(integers, company annual revenue in USD)."
    ),
    "smartlead": (
        "job_titles (list of strings), city, state, country, domain (a "
        "specific company website domain if one is named), keywords (free "
        "text, matched against company name/description), department (list "
        "of strings, e.g. \"Sales\", \"Engineering\"), level (list of "
        "strings, e.g. \"Manager\", \"Director\", \"VP\", \"C-Suite\", "
        "\"Staff\"), companyIndustry (list of strings), companySubIndustry "
        "(list of strings), companyHeadCount (list of strings, e.g. "
        "\"1 - 10\", \"1K - 10K\"), companyRevenue (list of strings, e.g. "
        "\"$1M - $10M\", \"> $1B\")."
    ),
}


class ProspectPromptService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.provider_configs = ProviderConfigRepository(session)

    async def parse(self, *, prompt: str, target_provider: str, workspace_id: uuid.UUID) -> dict:
        schema = _SCHEMA_DESCRIPTIONS.get(target_provider)
        if schema is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"AI prompt parsing isn't available for provider '{target_provider}'.",
            )

        instructions = (
            "Extract prospect-search filters from the user's sentence below. "
            f"Only use these field names, all optional: {schema} "
            "Only include a field if the sentence actually implies it — never "
            "guess or invent a value for something it doesn't mention. Omit "
            "fields entirely rather than filling them with a default or "
            "placeholder. Respond with a single flat JSON object using only "
            "the field names above."
        )

        registry_entries = await self.provider_configs.list_enabled_for_category(ProviderCategory.AI)
        if not registry_entries:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No AI provider is enabled in the registry")

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
                    operation="parse_prospect_prompt",
                    workspace_id=workspace_id,
                ) as usage:
                    result = await provider.generate(
                        AIGenerationRequest(
                            prompt_version=PROMPT_VERSION,
                            instructions=instructions,
                            source_fields={"prompt": prompt},
                        )
                    )
                    parsed = self._parse_result_text(result.text)
                    usage.records_returned = 1
            except ProviderUnavailableError as exc:
                logger.warning(
                    "prospect_prompt_provider_unavailable", provider=registry_entry.provider, error=str(exc)
                )
                last_error = str(exc)
                continue

            logger.info("prospect_prompt_parsed", provider=registry_entry.provider, target=target_provider)
            return parsed

        if len(missing_credentials) == len(registry_entries):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"No enabled AI provider has credentials configured (missing: {', '.join(missing_credentials)}).",
            )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"All enabled AI providers failed. Last error: {last_error}")

    def _parse_result_text(self, text: str) -> dict:
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise ProviderUnavailableError(f"AI response was not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ProviderUnavailableError("AI response JSON was not an object")
        return parsed
