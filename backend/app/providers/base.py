"""Shared provider contracts.

Every provider integration (Apollo, Smartlead, Anthropic, SMTP, ...) implements
one of the ABCs in the sibling `app/providers/<category>/base.py` modules.
The core application (services, API routes) only ever depends on these
interfaces — never on a concrete provider class — so providers can be
added, removed, or reordered without touching business logic.

A provider must never fabricate data. If a field is unknown, it returns
None; if a whole record can't be produced, it returns None/empty list.
Every normalized record carries `ProviderMetadata` so the caller can record
provenance (who supplied this field, and when).
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ProviderCategory(StrEnum):
    COMPANY_DISCOVERY = "company_discovery"
    PERSON_DISCOVERY = "person_discovery"
    AI = "ai"
    EMAIL_SENDER = "email_sender"


class ProviderUnavailableError(Exception):
    """Raised when a provider cannot serve a request (missing credentials,
    rate-limited, outage, ...). Orchestrators catch this and fall back to
    the next provider in priority order rather than failing the whole
    operation."""


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Provenance for a single normalized record returned by a provider.

    Callers persist this alongside the record (see CompanySource/
    ContactSource) so the UI can show e.g. "Email found by Hunter".
    """

    provider: str
    external_id: str | None = None
    source_url: str | None = None
    source_type: str = "api"
    raw_reference: dict[str, Any] = field(default_factory=dict)
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class NormalizedCompany:
    """Fields a discovery/enrichment provider may supply about a company.

    Every field is optional — a provider is never required to populate all
    of them, and the caller must never invent a value for a missing one.
    """

    metadata: ProviderMetadata
    name: str | None = None
    domain: str | None = None
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    industry: str | None = None
    category: str | None = None
    employee_count: int | None = None
    description: str | None = None
    linkedin_url: str | None = None
    social_urls: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedContact:
    """Fields a discovery/enrichment provider may supply about a person."""

    metadata: ProviderMetadata
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    seniority: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    #: This person's own location, when a provider reports it per-person
    #: rather than only at the company level.
    city: str | None = None
    state: str | None = None
    country: str | None = None
    #: Firmographic fields a provider reports alongside this specific
    #: search result (see Contact model for why these live here, not on
    #: Company, and why bands are kept as-is rather than parsed).
    industry: str | None = None
    sub_industry: str | None = None
    company_headcount: str | None = None
    company_revenue: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryCriteria:
    """Normalized search criteria passed to discovery providers.

    Providers ignore filters they don't support rather than erroring —
    the orchestrator is responsible for telling the user which filters a
    given provider actually honored.
    """

    keywords: str | None = None
    industry: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    company_name: str | None = None
    domain: str | None = None
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    job_titles: list[str] = field(default_factory=list)
    seniorities: list[str] = field(default_factory=list)
    limit: int = 25
    #: Smartlead has no free-text search — every call is scoped to one
    #: existing campaign. Other providers ignore this field.
    campaign_id: str | None = None
    #: Passthrough filters a specific provider understands but that don't
    #: warrant a first-class field here (e.g. Smartlead's emailStatus).
    extra_filters: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Common identity every concrete provider must expose."""

    #: Machine-readable provider name, e.g. "apollo", "smartlead", "csv_import".
    name: str
    category: ProviderCategory

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
