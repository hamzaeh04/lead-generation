import json

import httpx
import pytest

from app.providers.base import DiscoveryCriteria, ProviderUnavailableError
from app.providers.lead_sources.apollo_provider import ApolloCompanyDiscoveryProvider
from app.providers.people_sources.apollo_provider import ApolloPersonDiscoveryProvider

pytestmark = pytest.mark.asyncio


def _client_with(payload: dict, *, on_request=None, status_code: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == "test-key"
        if on_request is not None:
            on_request(request)
        return httpx.Response(status_code, json=payload)

    return httpx.AsyncClient(base_url="https://api.apollo.io", transport=httpx.MockTransport(handler))


async def test_discover_companies_maps_fields():
    payload = {
        "organizations": [
            {
                "id": "org-1",
                "name": "Acme Dental Group",
                "primary_domain": "acmedental.example",
                "website_url": "https://acmedental.example",
                "phone": "+15550100001",
                "city": "Miami",
                "state": "FL",
                "country": "US",
                "industry": "dental",
                "estimated_num_employees": 12,
                "linkedin_url": "https://linkedin.com/company/acme-dental",
            }
        ]
    }
    provider = ApolloCompanyDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_companies(DiscoveryCriteria(industry="dental", state="FL"))

    assert len(results) == 1
    assert results[0].name == "Acme Dental Group"
    assert results[0].domain == "acmedental.example"
    assert results[0].employee_count == 12
    assert results[0].metadata.provider == "apollo"
    assert results[0].metadata.external_id == "org-1"


async def test_discover_people_hits_current_search_endpoint():
    captured = {}

    def on_request(request):
        captured["path"] = request.url.path

    payload = {"people": []}
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload, on_request=on_request))

    await provider.discover_people(DiscoveryCriteria())

    assert captured["path"] == "/api/v1/mixed_people/api_search"


async def test_discover_people_request_uses_real_apollo_param_names():
    captured = {}

    def on_request(request):
        captured["body"] = request.content

    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with({"people": []}, on_request=on_request))

    await provider.discover_people(
        DiscoveryCriteria(
            job_titles=["CEO", "Founder"],
            seniorities=["c_suite", "founder"],
            city="Austin",
            state="TX",
            employee_count_min=10,
            employee_count_max=200,
            domain="acme.example",
            keywords="roofing",
            extra_filters={"technologies": ["salesforce"], "email_status": ["verified"]},
        )
    )

    body = json.loads(captured["body"])
    assert body["person_titles"] == ["CEO", "Founder"]
    assert body["person_seniorities"] == ["c_suite", "founder"]
    assert body["person_locations"] == ["Austin, TX"]
    assert body["organization_num_employees_ranges"] == ["10,200"]
    assert body["q_organization_domains_list"] == ["acme.example"]
    assert body["q_keywords"] == "roofing"
    assert body["currently_using_any_of_technology_uids"] == ["salesforce"]
    assert body["contact_email_status"] == ["verified"]


async def test_discover_people_never_stores_email_or_obfuscated_last_name():
    """api_search returns masked data — no email field at all, and last
    name only as last_name_obfuscated. Neither should ever end up stored
    as if it were real, regardless of what a (possibly stale/mocked)
    payload contains."""
    payload = {
        "people": [
            {
                "id": "person-1",
                "first_name": "Jordan",
                "last_name_obfuscated": "Al***z",
                "title": "Owner",
                "has_email": True,
                "organization": {"name": "Acme Dental Group", "primary_domain": "acmedental.example"},
            }
        ]
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["Owner"]))

    assert len(results) == 1
    assert results[0].email is None
    assert results[0].last_name is None
    assert results[0].full_name == "Jordan"
    assert results[0].metadata.external_id == "person-1"
    assert results[0].job_title == "Owner"
    assert results[0].company_domain == "acmedental.example"


async def test_reveal_maps_real_fields():
    payload = {
        "person": {
            "email": "sam@sunshineroofing.example",
            "first_name": "Sam",
            "last_name": "Chen",
            "name": "Sam Chen",
            "phone_numbers": [{"sanitized_number": "+15550100002", "raw_number": "555-0100002"}],
        }
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.reveal("person-2")

    assert result == {
        "first_name": "Sam",
        "last_name": "Chen",
        "full_name": "Sam Chen",
        "email": "sam@sunshineroofing.example",
        "email_status": None,
        "phone": "+15550100002",
        "linkedin_url": None,
        "city": None,
        "state": None,
        "country": None,
        "seniority": None,
        "department": None,
        "organization": None,
    }


async def test_reveal_maps_full_enrichment_including_organization():
    payload = {
        "person": {
            "email": "larry@blackrock.example",
            "first_name": "Larry",
            "last_name": "Fink",
            "name": "Larry Fink",
            "email_status": "verified",
            "linkedin_url": "http://www.linkedin.com/in/laurencefink",
            "city": "New York",
            "state": "New York",
            "country": "United States",
            "seniority": "c_suite",
            "departments": ["c_suite"],
            "organization": {
                "industry": "financial services",
                "estimated_num_employees": 27000,
                "organization_revenue": 24216000000.0,
                "founded_year": 1988,
                "website_url": "blackrock.com",
                "primary_phone": "+12125551000",
                "linkedin_url": "http://www.linkedin.com/company/blackrock",
                "city": "New York",
                "state": "New York",
                "country": "United States",
            },
        }
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.reveal("person-3")

    assert result is not None
    assert result["email_status"] == "verified"
    assert result["linkedin_url"] == "http://www.linkedin.com/in/laurencefink"
    assert result["seniority"] == "c_suite"
    assert result["department"] == "c_suite"
    assert result["city"] == "New York"
    org = result["organization"]
    assert org["industry"] == "financial services"
    assert org["employee_count"] == 27000
    assert org["annual_revenue"] == 24216000000.0
    assert org["founded_year"] == 1988
    assert org["website"] == "blackrock.com"
    assert org["phone"] == "+12125551000"


async def test_reveal_filters_locked_email_placeholder():
    payload = {
        "person": {
            "email": "email_not_unlocked@acmedental.example",
            "first_name": "Jordan",
            "last_name": "Alvarez",
        }
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.reveal("person-1")

    assert result is not None
    assert result["email"] is None  # locked placeholder must never be stored as a real email
    assert result["last_name"] == "Alvarez"  # still useful even without email


async def test_reveal_returns_none_when_apollo_has_nothing():
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with({"person": None}))

    assert await provider.reveal("unknown-id") is None


async def test_reveal_returns_none_when_person_missing_entirely():
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with({}))

    assert await provider.reveal("unknown-id") is None


async def test_discover_decision_makers_hits_current_search_endpoint_and_masks():
    captured = {}

    def on_request(request):
        captured["path"] = request.url.path

    payload = {
        "people": [
            {
                "id": "person-3",
                "first_name": "Robin",
                "last_name_obfuscated": "Sm***h",
                "title": "Owner",
                "organization": {"name": "Acme Dental Group", "primary_domain": "acmedental.example"},
            }
        ]
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload, on_request=on_request))

    results = await provider.discover_decision_makers("acmedental.example", ["Owner"])

    assert captured["path"] == "/api/v1/mixed_people/api_search"
    assert len(results) == 1
    assert results[0].email is None
    assert results[0].last_name is None


async def test_missing_api_key_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        ApolloCompanyDiscoveryProvider(api_key="")
    with pytest.raises(ProviderUnavailableError):
        ApolloPersonDiscoveryProvider(api_key="")
