"""Smartlead person discovery — two distinct modes on two distinct hosts.

1. Campaign-lead pull (original mode): GET server.smartlead.ai's
   /campaigns/{id}/leads — fetches leads already sitting in a campaign you
   built inside Smartlead's own app. Selected when criteria.campaign_id is
   set.
2. SmartProspect search (added Sep 2026): POST prospect-api.smartlead.ai's
   /api/v1/search-email-leads/search-contacts — real prospecting against
   Smartlead's 270M+ profile database. Selected when campaign_id is absent.
   Verified directly against api.smartlead.ai/api-reference/smart-prospect/
   search-contacts: request is structured filters only (no free-text prompt
   field — Smartlead's own "Ask AI" box in their web app translates a
   sentence into these same filters before calling this endpoint, which is
   why our own AI-prompt UX does the same via ProspectPromptService before
   ever reaching this provider). Like Apollo, an unpurchased/locked result
   is MASKED — but instead of an obviously-blank field, Smartlead fills
   email/linkedin with a literal placeholder ("random@example.com" /
   "linkedin.com/random_data") on every locked record. _to_prospect_contact
   strips that placeholder back to None so it's never stored as if real,
   and so two different locked people don't collide on the same fake email
   during contact dedup. There is no documented API endpoint to unlock a
   masked result (unlocking is dashboard-only), so unlike Apollo this
   provider has no reveal() override — masked leads stay masked until
   someone unlocks them in Smartlead's own UI.

Auth for both modes is a query-param `api_key`, not a header — unlike every
other provider in this codebase.

Requires SMARTLEAD_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    DiscoveryCriteria,
    NormalizedContact,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.http import request_json
from app.providers.people_sources.base import PersonDiscoveryProvider

_CAMPAIGN_BASE_URL = "https://server.smartlead.ai"

# SmartProspect fills these exact literals into every LOCKED (unpurchased)
# result's email/linkedin fields — not a real value for anyone. Stored
# as-is, they'd violate "never fabricate data" and — since it's the same
# literal for every locked person — collapse unrelated people into one
# contact during dedup (matching is keyed on email/linkedin equality).
_MASKED_EMAIL = "random@example.com"
_MASKED_LINKEDIN = "linkedin.com/random_data"
_PROSPECT_BASE_URL = "https://prospect-api.smartlead.ai"

_CAMPAIGN_PASSTHROUGH_FILTER_KEYS = (
    "status",
    "emailStatus",
    "lead_category_id",
    "created_at_gt",
    "last_sent_time_gt",
    "event_time_gt",
)

# SmartProspect's real filter field names (verified against Smartlead's docs),
# passed straight through from extra_filters — see module docstring.
_PROSPECT_FILTER_KEYS = (
    "title",
    "includeTitle",
    "excludeTitle",
    "titleExactMatch",
    "department",
    "level",
    "companyName",
    "companyDomain",
    "includeCompany",
    "excludeCompany",
    "companyKeyword",
    "companyHeadCount",
    "companyRevenue",
    "companyIndustry",
    "companySubIndustry",
    "city",
    "state",
    "country",
    "scroll_id",
)


class SmartleadPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "smartlead"
    category = ProviderCategory.PERSON_DISCOVERY

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        prospect_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("smartlead: SMARTLEAD_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=_CAMPAIGN_BASE_URL, timeout=httpx.Timeout(15.0))
        self._prospect_client = prospect_client or httpx.AsyncClient(
            base_url=_PROSPECT_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        if criteria.campaign_id:
            return await self._discover_from_campaign(criteria)
        return await self._discover_from_smartprospect(criteria)

    async def _discover_from_campaign(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        params: dict = {
            "api_key": self._api_key,
            "offset": 0,
            "limit": min(criteria.limit, 100),
        }
        for key in _CAMPAIGN_PASSTHROUGH_FILTER_KEYS:
            value = criteria.extra_filters.get(key)
            if value is not None:
                params[key] = value

        payload = await request_json(
            self._client,
            "GET",
            f"/api/v1/campaigns/{criteria.campaign_id}/leads",
            provider=self.name,
            params=params,
        )
        leads = payload.get("leads") or []
        return [self._to_campaign_contact(lead) for lead in leads[: criteria.limit]]

    async def _discover_from_smartprospect(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        body: dict = {"limit": min(criteria.limit, 500)}
        if criteria.job_titles:
            body["title"] = criteria.job_titles
        if criteria.city:
            body["city"] = [criteria.city]
        if criteria.state:
            body["state"] = [criteria.state]
        if criteria.country:
            body["country"] = [criteria.country]
        if criteria.domain:
            body["companyDomain"] = [criteria.domain]
        if criteria.keywords:
            body["companyKeyword"] = [criteria.keywords]
        for key in _PROSPECT_FILTER_KEYS:
            value = criteria.extra_filters.get(key)
            if value is not None:
                body[key] = value

        payload = await request_json(
            self._prospect_client,
            "POST",
            "/api/v1/search-email-leads/search-contacts",
            provider=self.name,
            params={"api_key": self._api_key},
            json=body,
        )
        data = payload.get("data") or {}
        leads = data.get("list") or []
        # filter_id scopes this exact search — Smartlead's support-confirmed
        # (not yet documented) unlock flow uses it to reveal emails for
        # specific contacts from the search. No unlock endpoint is wired up
        # yet (its real URL/params are pending Smartlead support), but we
        # keep filter_id on each contact's raw_reference now so it isn't
        # lost — wiring reveal() in later needs only this value plus the
        # contact's external_id, not a re-search.
        filter_id = data.get("filter_id")
        return [self._to_prospect_contact(lead, filter_id=filter_id) for lead in leads[: criteria.limit]]

    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        raise ProviderUnavailableError(
            "smartlead: decision-maker lookup by company domain is not supported — "
            "use SmartProspect search (company + title filters) instead"
        )

    def _to_campaign_contact(self, lead: dict) -> NormalizedContact:
        first_name = lead.get("first_name")
        last_name = lead.get("last_name")
        full_name = " ".join(part for part in (first_name, last_name) if part) or None
        return NormalizedContact(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=str(lead["id"]) if lead.get("id") is not None else None,
                source_type="api",
                raw_reference=lead,
            ),
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=lead.get("email"),
            company_name=lead.get("company_name"),
        )

    def _to_prospect_contact(self, lead: dict, *, filter_id: int | str | None = None) -> NormalizedContact:
        company = lead.get("company") or {}
        first_name = lead.get("firstName")
        last_name = lead.get("lastName")
        departments = lead.get("department")
        email = self._unmask(lead.get("email"), _MASKED_EMAIL)
        linkedin = self._unmask(lead.get("linkedin"), _MASKED_LINKEDIN)
        raw_reference = {**lead, "_smartlead_filter_id": filter_id} if filter_id is not None else lead
        return NormalizedContact(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=str(lead["id"]) if lead.get("id") is not None else None,
                source_url=self._linkedin_url(linkedin),
                source_type="api",
                raw_reference=raw_reference,
            ),
            first_name=first_name,
            last_name=last_name,
            full_name=lead.get("fullName") or " ".join(p for p in (first_name, last_name) if p) or None,
            job_title=lead.get("title"),
            department=departments[0] if isinstance(departments, list) and departments else None,
            seniority=lead.get("level"),
            email=email,
            linkedin_url=self._linkedin_url(linkedin),
            company_name=company.get("name"),
            company_domain=company.get("website"),
            city=lead.get("city") or None,
            state=lead.get("state") or None,
            country=lead.get("country") or None,
            industry=lead.get("industry"),
            sub_industry=lead.get("subIndustry"),
            company_headcount=lead.get("companyHeadCount"),
            company_revenue=lead.get("companyRevenue"),
        )

    @staticmethod
    def _unmask(value: str | None, masked_literal: str) -> str | None:
        return None if value == masked_literal else value

    @staticmethod
    def _linkedin_url(linkedin: str | None) -> str | None:
        if not linkedin:
            return None
        return linkedin if linkedin.startswith("http") else f"https://{linkedin}"
