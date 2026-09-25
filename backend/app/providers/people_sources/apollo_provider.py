"""Apollo.io people search (person discovery) + reveal (enrichment).

Verified against Apollo's current docs (docs.apollo.io/reference/people-api-search
and .../people-enrichment) in September 2026 — the older `mixed_people/search`
endpoint this file used to call is deprecated/plan-restricted; the current
prospecting endpoint is `mixed_people/api_search`.

Two-step flow, matching Apollo's own product UX:
  1. `discover_people` (this file) — free (0 credits), but the response is
     masked: no email, and even the last name comes back obfuscated
     (e.g. "Sm***h"). We never store that obfuscated value or a fabricated
     placeholder — `last_name`/`email`/`phone` stay None until revealed.
  2. `reveal` (this file) — costs Apollo credits per person, called
     on-demand later (see app/api/v1/leads.py's /reveal endpoint), not
     automatically for every search result.

Requires APOLLO_API_KEY.
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

_BASE_URL = "https://api.apollo.io"

# extra_filters keys passed straight through to Apollo's advanced params —
# left out of DiscoveryCriteria's named fields since they're Apollo-specific
# and the orchestrator's contract is "providers ignore filters they don't
# support," not "every provider gets a first-class field." Friendly names
# here (not Apollo's raw param names) so the AI prompt-parsing service can
# target one human-readable vocabulary across providers; translated to
# Apollo's actual API param names in _search_body.
_FRIENDLY_TO_APOLLO_PARAM = {
    "email_status": "contact_email_status",  # list[str]: verified/unverified/likely to engage/unavailable
    "technologies": "currently_using_any_of_technology_uids",  # list[str]
    "organization_locations": "organization_locations",  # list[str] — company HQ, distinct from person_locations
}


class ApolloPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "apollo"
    category = ProviderCategory.PERSON_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("apollo: APOLLO_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        body = self._search_body(criteria)
        payload = await request_json(
            self._client,
            "POST",
            "/api/v1/mixed_people/api_search",
            provider=self.name,
            headers={"x-api-key": self._api_key},
            json=body,
        )
        people = payload.get("people") or []
        return [self._to_masked_contact(p) for p in people[: criteria.limit]]

    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        body: dict = {
            "page": 1,
            "per_page": 25,
            "q_organization_domains_list": [company_domain],
        }
        if target_titles:
            body["person_titles"] = target_titles
        payload = await request_json(
            self._client,
            "POST",
            "/api/v1/mixed_people/api_search",
            provider=self.name,
            headers={"x-api-key": self._api_key},
            json=body,
        )
        people = payload.get("people") or []
        return [self._to_masked_contact(p) for p in people]

    async def reveal(self, person_id: str, *, raw_reference: dict | None = None) -> dict | None:
        """Enriches one masked search result into full contact + company
        details — Apollo's /people/match response includes far more than
        email/phone (real location, seniority, department, deliverability
        status, and a nested `organization` object with precise employee
        count/revenue/founding year), and this returns all of it rather
        than just the identity fields.

        Returns None (never an error) when Apollo has nothing to reveal —
        an empty match is a normal outcome, not a failure, same convention
        as every other "nothing found" path in this codebase. Once
        `revealed_for_current_team` is true, Apollo does not re-bill this
        call for the same person.
        """
        payload = await request_json(
            self._client,
            "POST",
            "/api/v1/people/match",
            provider=self.name,
            headers={"x-api-key": self._api_key},
            json={"id": person_id},
        )
        person = payload.get("person")
        if not person:
            return None
        email = self._real_email_or_none(person.get("email"))
        phone = self._first_phone_number(person)
        first_name = person.get("first_name")
        last_name = person.get("last_name")
        if not email and not phone and not last_name:
            # Apollo matched the id but revealed nothing new — treat the
            # same as no match rather than "successfully revealed nothing."
            return None

        departments = person.get("departments")
        org = person.get("organization")
        return {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": person.get("name") or " ".join(p for p in (first_name, last_name) if p) or None,
            "email": email,
            "email_status": person.get("email_status"),
            "phone": phone,
            "linkedin_url": person.get("linkedin_url"),
            "city": person.get("city"),
            "state": person.get("state"),
            "country": person.get("country"),
            "seniority": person.get("seniority"),
            "department": departments[0] if isinstance(departments, list) and departments else None,
            "organization": self._org_enrichment(org) if isinstance(org, dict) else None,
        }

    async def request_phone_reveal(self, external_id: str, *, webhook_url: str) -> None:
        """Kicks off Apollo's async mobile/direct-dial phone reveal.

        Verified against docs.apollo.io/reference/people-enrichment and
        .../docs/retrieve-mobile-phone-numbers-for-contacts (September
        2026): passing `reveal_phone_number: true` requires a `webhook_url`
        — Apollo returns its normal synchronous /people/match response
        immediately (which we ignore here; email/name were already
        captured by reveal()), then separately POSTs the actual phone
        number(s) to that webhook once the lookup completes, in the shape
        `{"people": [{"id": ..., "phone_numbers": [...]}], ...}` (see
        app/api/v1/webhooks.py's /apollo/phone-reveal handler). Costs 8
        Apollo credits only if a mobile number is actually found — nothing
        is charged for a miss.
        """
        await request_json(
            self._client,
            "POST",
            "/api/v1/people/match",
            provider=self.name,
            headers={"x-api-key": self._api_key},
            json={"id": external_id, "reveal_phone_number": True, "webhook_url": webhook_url},
        )

    @staticmethod
    def _org_enrichment(org: dict) -> dict:
        """Only the fields we actually persist onto Company — Apollo's
        organization object has ~30 fields, most not worth a schema
        column yet (sic/naics codes, social profiles, etc.)."""
        return {
            "industry": org.get("industry"),
            "employee_count": org.get("estimated_num_employees"),
            "annual_revenue": org.get("organization_revenue") or org.get("annual_revenue"),
            "founded_year": org.get("founded_year"),
            "website": org.get("website_url"),
            "phone": org.get("phone") or org.get("primary_phone"),
            "linkedin_url": org.get("linkedin_url"),
            "city": org.get("city"),
            "state": org.get("state"),
            "country": org.get("country"),
        }

    def _search_body(self, criteria: DiscoveryCriteria) -> dict:
        body: dict = {"page": 1, "per_page": min(criteria.limit, 100)}
        if criteria.domain:
            body["q_organization_domains_list"] = [criteria.domain]
        if criteria.job_titles:
            body["person_titles"] = criteria.job_titles
        if criteria.seniorities:
            body["person_seniorities"] = criteria.seniorities
        if criteria.keywords:
            body["q_keywords"] = criteria.keywords
        locations = [p for p in (criteria.city, criteria.state, criteria.country) if p]
        if locations:
            body["person_locations"] = [", ".join(locations)]
        if criteria.employee_count_min is not None or criteria.employee_count_max is not None:
            lo = criteria.employee_count_min if criteria.employee_count_min is not None else 0
            hi = criteria.employee_count_max if criteria.employee_count_max is not None else 1000000
            body["organization_num_employees_ranges"] = [f"{lo},{hi}"]
        for friendly_key, apollo_param in _FRIENDLY_TO_APOLLO_PARAM.items():
            value = criteria.extra_filters.get(friendly_key)
            if value is not None:
                body[apollo_param] = value
        revenue_min = criteria.extra_filters.get("revenue_min")
        revenue_max = criteria.extra_filters.get("revenue_max")
        if revenue_min is not None or revenue_max is not None:
            body["revenue_range"] = {
                k: v for k, v in {"min": revenue_min, "max": revenue_max}.items() if v is not None
            }
        return body

    def _to_masked_contact(self, person: dict) -> NormalizedContact:
        org = person.get("organization") or {}
        first_name = person.get("first_name")
        return NormalizedContact(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=person.get("id"),
                source_type="api",
                raw_reference=person,
            ),
            first_name=first_name,
            last_name=None,  # Apollo only returns last_name_obfuscated pre-reveal — never store that
            full_name=first_name,
            job_title=person.get("title"),
            seniority=person.get("seniority"),
            company_name=org.get("name"),
            company_domain=org.get("primary_domain"),
            # email/phone/linkedin intentionally left None — masked until reveal()
        )

    @staticmethod
    def _real_email_or_none(email: str | None) -> str | None:
        """Apollo returns a literal 'email_not_unlocked@domain.com' placeholder
        when the address hasn't been unlocked with reveal credits — that is
        not a real discovered email and must never be stored as one."""
        if not email or email.startswith("email_not_unlocked"):
            return None
        return email

    @staticmethod
    def _first_phone_number(person: dict) -> str | None:
        """Apollo returns `phone_numbers` as a list of
        {raw_number, sanitized_number, type, ...} objects; take the first
        entry's sanitized (E.164-style) number, falling back to raw."""
        numbers = person.get("phone_numbers")
        if not isinstance(numbers, list) or not numbers:
            return None
        first = numbers[0]
        if not isinstance(first, dict):
            return None
        return first.get("sanitized_number") or first.get("raw_number")
