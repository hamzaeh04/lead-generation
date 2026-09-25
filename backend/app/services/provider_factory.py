"""Builds a concrete provider instance for a (provider name, category) pair.

Credentials resolve in order:
1. Workspace row in `workspace_api_keys` (Settings UI), when a workspace is known
2. Process env / Settings (.env / Vercel env vars)

Returns None when no key is available — callers turn that into a clear
"provider not configured" response rather than a crash.

Active builders: Apollo (company + person discovery), Smartlead (person
discovery via campaign leads), Anthropic (AI personalization). OpenAI and
SMTP stay commented out (inert, not deleted) pending future work — same
pattern as before, not something this trim touches. Groq was fully
removed (not just disabled): its free tier's per-minute output-token cap
made batch qualification impractically slow, and Anthropic replaced it
outright rather than staying around as an inert alternative.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.workspace_api_keys import WorkspaceApiKeys
from app.providers.ai.anthropic_provider import AnthropicProvider
# from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.base import BaseProvider, ProviderCategory, ProviderUnavailableError
# from app.providers.email_senders.smtp_provider import SMTPEmailSenderProvider
from app.providers.lead_sources.apollo_provider import ApolloCompanyDiscoveryProvider
from app.providers.people_sources.apollo_provider import ApolloPersonDiscoveryProvider
from app.providers.people_sources.smartlead_provider import SmartleadPersonDiscoveryProvider
from app.repositories.workspace_api_keys_repository import WorkspaceApiKeysRepository

_BUILDERS: dict[tuple[str, ProviderCategory], tuple[str | None, type]] = {
    ("apollo", ProviderCategory.COMPANY_DISCOVERY): ("APOLLO_API_KEY", ApolloCompanyDiscoveryProvider),
    ("apollo", ProviderCategory.PERSON_DISCOVERY): ("APOLLO_API_KEY", ApolloPersonDiscoveryProvider),
    ("smartlead", ProviderCategory.PERSON_DISCOVERY): (
        "SMARTLEAD_API_KEY", SmartleadPersonDiscoveryProvider,
    ),
    ("anthropic", ProviderCategory.AI): ("ANTHROPIC_API_KEY", AnthropicProvider),
    # ("openai", ProviderCategory.AI): ("OPENAI_API_KEY", OpenAIProvider),
    # ("smtp", ProviderCategory.EMAIL_SENDER): ("SMTP_HOST", SMTPEmailSenderProvider),
}


# Credential env-var per provider, kept independent of _BUILDERS so that
# "not configured" error messages stay accurate even for providers whose
# builder entry above is commented out.
_ENV_VARS: dict[str, str] = {
    "apollo": "APOLLO_API_KEY",
    "smartlead": "SMARTLEAD_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "smtp": "SMTP_HOST",
}

# Workspace DB column for each provider (Settings → Provider API keys).
_DB_KEY_FIELDS: dict[str, str] = {
    "apollo": "apollo_api_key",
    "smartlead": "smartlead_api_key",
    "anthropic": "anthropic_api_key",
}


def required_env_var(provider_name: str, category: ProviderCategory) -> str | None:
    entry = _BUILDERS.get((provider_name, category))
    if entry:
        return entry[0]
    return _ENV_VARS.get(provider_name)


def resolve_api_key(
    provider_name: str,
    settings: Settings,
    workspace_keys: WorkspaceApiKeys | None = None,
) -> str | None:
    """Prefer workspace DB key; fall back to .env / process settings."""
    field = _DB_KEY_FIELDS.get(provider_name)
    if workspace_keys is not None and field:
        db_value = getattr(workspace_keys, field, None)
        if isinstance(db_value, str) and db_value.strip():
            return db_value.strip()

    env_var = _ENV_VARS.get(provider_name)
    if env_var:
        env_value = getattr(settings, env_var, None)
        if isinstance(env_value, str) and env_value.strip():
            return env_value.strip()
    return None


def build_provider(
    provider_name: str,
    category: ProviderCategory,
    settings: Settings,
    *,
    api_key: str | None = None,
) -> BaseProvider | None:
    entry = _BUILDERS.get((provider_name, category))
    if entry is None:
        return None
    env_var, provider_cls = entry
    if env_var is None:
        return provider_cls()

    # Explicit api_key (already resolved from DB/.env) wins; otherwise env only.
    key = api_key if api_key is not None else getattr(settings, env_var, None)
    if isinstance(key, str):
        key = key.strip() or None
    if not key:
        return None
    if provider_cls is AnthropicProvider:
        return AnthropicProvider(api_key=key, model=settings.ANTHROPIC_MODEL)
    return provider_cls(api_key=key)


async def build_provider_for_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider_name: str,
    category: ProviderCategory,
    settings: Settings,
) -> BaseProvider | None:
    """Load workspace_api_keys then build with DB → .env credential resolution."""
    row = await WorkspaceApiKeysRepository(session).get_for_workspace(workspace_id)
    api_key = resolve_api_key(provider_name, settings, row)
    return build_provider(provider_name, category, settings, api_key=api_key)
