"""Builds a concrete provider instance for a (provider name, category) pair.

Returns None when the required API key isn't configured — callers turn
that into a clear "provider not configured" response rather than a crash.
This is the one place in the codebase that knows about concrete provider
classes; everything else depends only on the ABCs in app/providers/base.py.

Active builders: Apollo (company + person discovery), Smartlead (person
discovery via campaign leads), Groq (AI personalization). OpenAI and SMTP
stay commented out (inert, not deleted) pending future work — same
pattern as before, not something this trim touches.
"""
from __future__ import annotations

from app.core.config import Settings
# from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.ai.groq_provider import GroqProvider
from app.providers.base import BaseProvider, ProviderCategory, ProviderUnavailableError
# from app.providers.email_senders.smtp_provider import SMTPEmailSenderProvider
from app.providers.lead_sources.apollo_provider import ApolloCompanyDiscoveryProvider
from app.providers.people_sources.apollo_provider import ApolloPersonDiscoveryProvider
from app.providers.people_sources.smartlead_provider import SmartleadPersonDiscoveryProvider

_BUILDERS: dict[tuple[str, ProviderCategory], tuple[str | None, type]] = {
    ("apollo", ProviderCategory.COMPANY_DISCOVERY): ("APOLLO_API_KEY", ApolloCompanyDiscoveryProvider),
    ("apollo", ProviderCategory.PERSON_DISCOVERY): ("APOLLO_API_KEY", ApolloPersonDiscoveryProvider),
    ("smartlead", ProviderCategory.PERSON_DISCOVERY): (
        "SMARTLEAD_API_KEY", SmartleadPersonDiscoveryProvider,
    ),
    ("groq", ProviderCategory.AI): ("GROQ_API_KEY", GroqProvider),
    # ("openai", ProviderCategory.AI): ("OPENAI_API_KEY", OpenAIProvider),
    # ("smtp", ProviderCategory.EMAIL_SENDER): ("SMTP_HOST", SMTPEmailSenderProvider),
}


# Credential env-var per provider, kept independent of _BUILDERS so that
# "not configured" error messages stay accurate even for providers whose
# builder entry above is commented out.
_ENV_VARS: dict[str, str] = {
    "apollo": "APOLLO_API_KEY",
    "smartlead": "SMARTLEAD_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "smtp": "SMTP_HOST",
}


def required_env_var(provider_name: str, category: ProviderCategory) -> str | None:
    entry = _BUILDERS.get((provider_name, category))
    if entry:
        return entry[0]
    return _ENV_VARS.get(provider_name)


def build_provider(
    provider_name: str, category: ProviderCategory, settings: Settings
) -> BaseProvider | None:
    entry = _BUILDERS.get((provider_name, category))
    if entry is None:
        return None
    env_var, provider_cls = entry
    if env_var is None:
        return provider_cls()

    # SMTP and OpenAI builders were here (needed non-standard construction:
    # SMTP takes host/port/username/password, OpenAI takes a model) — both
    # commented out above along with their _BUILDERS entries, so the
    # branches that referenced them are removed too. Restore alongside the
    # imports/_BUILDERS entries if re-enabling either provider.

    api_key = getattr(settings, env_var, None)
    if not api_key:
        return None
    if provider_cls is GroqProvider:
        return GroqProvider(api_key=api_key, model=settings.GROQ_MODEL)
    return provider_cls(api_key=api_key)
