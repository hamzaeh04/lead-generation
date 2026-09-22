import httpx
import pytest

from app.providers.base import DiscoveryCriteria, ProviderUnavailableError
from app.providers.people_sources.smartlead_provider import SmartleadPersonDiscoveryProvider


def _client_with(payload: dict, *, status_code: int = 200, on_request=None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if on_request is not None:
            on_request(request)
        return httpx.Response(status_code, json=payload)

    return httpx.AsyncClient(
        base_url="https://server.smartlead.ai", transport=httpx.MockTransport(handler)
    )


def _prospect_client_with(payload: dict, *, status_code: int = 200, on_request=None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if on_request is not None:
            on_request(request)
        return httpx.Response(status_code, json=payload)

    return httpx.AsyncClient(
        base_url="https://prospect-api.smartlead.ai", transport=httpx.MockTransport(handler)
    )


def test_missing_api_key_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        SmartleadPersonDiscoveryProvider(api_key="")


@pytest.mark.asyncio
async def test_discover_people_requires_campaign_id():
    called = False

    def on_request(request):
        nonlocal called
        called = True

    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({"leads": []}, on_request=on_request)
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.discover_people(DiscoveryCriteria())

    assert called is False


@pytest.mark.asyncio
async def test_discover_people_maps_fields():
    payload = {
        "total": 1,
        "leads": [
            {
                "id": 789,
                "email": "jordan@acmedental.example",
                "first_name": "Jordan",
                "last_name": "Alvarez",
                "company_name": "Acme Dental Group",
                "status": "INPROGRESS",
            }
        ],
        "offset": 0,
        "limit": 100,
    }
    provider = SmartleadPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_people(DiscoveryCriteria(campaign_id="123"))

    assert len(results) == 1
    contact = results[0]
    assert contact.email == "jordan@acmedental.example"
    assert contact.first_name == "Jordan"
    assert contact.last_name == "Alvarez"
    assert contact.full_name == "Jordan Alvarez"
    assert contact.company_name == "Acme Dental Group"
    assert contact.metadata.provider == "smartlead"
    assert contact.metadata.external_id == "789"


@pytest.mark.asyncio
async def test_discover_people_handles_missing_fields_without_crashing():
    payload = {"leads": [{"id": 1, "email": None}]}
    provider = SmartleadPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_people(DiscoveryCriteria(campaign_id="123"))

    assert len(results) == 1
    assert results[0].full_name is None
    assert results[0].email is None


@pytest.mark.asyncio
async def test_discover_people_truncates_to_limit():
    payload = {"leads": [{"id": i, "email": f"lead{i}@example.com"} for i in range(5)]}
    provider = SmartleadPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_people(DiscoveryCriteria(campaign_id="123", limit=3))

    assert len(results) == 3


@pytest.mark.asyncio
async def test_discover_people_passes_extra_filters_as_query_params():
    captured = {}

    def on_request(request):
        captured.update(dict(request.url.params))

    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({"leads": []}, on_request=on_request)
    )

    await provider.discover_people(
        DiscoveryCriteria(campaign_id="123", extra_filters={"status": "STARTED", "unknown_key": "x"})
    )

    assert captured["status"] == "STARTED"
    assert "unknown_key" not in captured
    assert captured["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_discover_people_raises_on_auth_failure():
    provider = SmartleadPersonDiscoveryProvider(
        api_key="bad-key", client=_client_with({"message": "Invalid API Key"}, status_code=401)
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.discover_people(DiscoveryCriteria(campaign_id="123"))


@pytest.mark.asyncio
async def test_discover_decision_makers_always_raises():
    provider = SmartleadPersonDiscoveryProvider(api_key="test-key", client=_client_with({}))

    with pytest.raises(ProviderUnavailableError):
        await provider.discover_decision_makers("acmedental.example", ["Owner"])


# ---------------------------------------------------------------------------
# SmartProspect mode (no campaign_id -> real prospecting search)
# ---------------------------------------------------------------------------

_PROSPECT_RESPONSE = {
    "success": True,
    "data": {
        "list": [
            {
                "id": "5f22b0e8cff47e0001616f81",
                "firstName": "Orhan",
                "lastName": "Demiri",
                "fullName": "Orhan Demiri",
                "title": "VP of Sales",
                "company": {"name": "Gothaer", "website": "gothaer.de"},
                "department": ["Sales"],
                "level": "VP",
                "industry": "Financial Services",
                "companyHeadCount": "1K - 10K",
                "companyRevenue": "> $1B",
                "country": "Germany",
                "email": "orhan@gothaer.de",
                "linkedin": "linkedin.com/in/orhan-demiri",
            }
        ],
        "scroll_id": "scroll-token",
        "filter_id": 327105,
        "total_count": 16064669,
    },
}


@pytest.mark.asyncio
async def test_discover_people_without_campaign_id_hits_smartprospect():
    captured = {}

    def on_request(request):
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)

    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key",
        client=_client_with({}),
        prospect_client=_prospect_client_with(_PROSPECT_RESPONSE, on_request=on_request),
    )

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["VP of Sales"], country="Germany"))

    assert captured["path"] == "/api/v1/search-email-leads/search-contacts"
    assert captured["params"]["api_key"] == "test-key"
    assert len(results) == 1
    contact = results[0]
    assert contact.first_name == "Orhan"
    assert contact.last_name == "Demiri"
    assert contact.full_name == "Orhan Demiri"
    assert contact.job_title == "VP of Sales"
    assert contact.email == "orhan@gothaer.de"
    assert contact.company_name == "Gothaer"
    assert contact.company_domain == "gothaer.de"
    assert contact.department == "Sales"
    assert contact.linkedin_url == "https://linkedin.com/in/orhan-demiri"
    assert contact.metadata.provider == "smartlead"
    assert contact.metadata.external_id == "5f22b0e8cff47e0001616f81"
    assert contact.seniority == "VP"
    assert contact.country == "Germany"
    assert contact.industry == "Financial Services"
    assert contact.company_headcount == "1K - 10K"
    assert contact.company_revenue == "> $1B"
    # filter_id isn't documented/unlockable via API yet, but must not be
    # discarded — a future reveal() implementation needs it.
    assert contact.metadata.raw_reference["_smartlead_filter_id"] == 327105


@pytest.mark.asyncio
async def test_smartprospect_request_maps_criteria_and_extra_filters():
    captured = {}

    def on_request(request):
        import json

        captured["body"] = json.loads(request.content)

    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key",
        client=_client_with({}),
        prospect_client=_prospect_client_with({"data": {"list": []}}, on_request=on_request),
    )

    await provider.discover_people(
        DiscoveryCriteria(
            job_titles=["CTO"],
            city="Berlin",
            state="Berlin",
            country="Germany",
            domain="acme.example",
            keywords="fintech",
            limit=10,
            extra_filters={"department": ["Engineering"], "level": ["C-Suite"], "companyHeadCount": ["1K - 10K"]},
        )
    )

    body = captured["body"]
    assert body["title"] == ["CTO"]
    assert body["city"] == ["Berlin"]
    assert body["state"] == ["Berlin"]
    assert body["country"] == ["Germany"]
    assert body["companyDomain"] == ["acme.example"]
    assert body["companyKeyword"] == ["fintech"]
    assert body["limit"] == 10
    assert body["department"] == ["Engineering"]
    assert body["level"] == ["C-Suite"]
    assert body["companyHeadCount"] == ["1K - 10K"]


@pytest.mark.asyncio
async def test_smartprospect_handles_missing_fields_without_crashing():
    payload = {"data": {"list": [{"id": "x", "email": None}]}}
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with(payload)
    )

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["CTO"]))

    assert len(results) == 1
    assert results[0].full_name is None
    assert results[0].email is None


@pytest.mark.asyncio
async def test_smartprospect_truncates_to_limit():
    payload = {"data": {"list": [{"id": str(i), "email": f"lead{i}@example.com"} for i in range(5)]}}
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with(payload)
    )

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["CTO"], limit=3))

    assert len(results) == 3


@pytest.mark.asyncio
async def test_smartprospect_normalizes_blank_location_to_none():
    """Smartlead sometimes returns city/state as an empty string rather
    than omitting the key — that's not a real value and must not be
    stored as one."""
    payload = {"data": {"list": [{"id": "1", "city": "", "state": "", "country": "United States"}]}}
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with(payload)
    )

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["CTO"]))

    assert results[0].city is None
    assert results[0].state is None
    assert results[0].country == "United States"


@pytest.mark.asyncio
async def test_smartprospect_strips_locked_placeholder_email_and_linkedin():
    """Regression test: SmartProspect fills email/linkedin with the exact
    same literal placeholder ("random@example.com" / "linkedin.com/
    random_data") on every locked/unpurchased result. Storing that as real
    data both violates "never fabricate" and collapses unrelated people
    into one contact during dedup, since matching is keyed on email
    equality. Two different locked people must come back with email=None,
    never the shared placeholder."""
    payload = {
        "data": {
            "list": [
                {
                    "id": "locked-1",
                    "firstName": "Lucy",
                    "lastName": "Lubertazzo",
                    "email": "random@example.com",
                    "linkedin": "linkedin.com/random_data",
                },
                {
                    "id": "locked-2",
                    "firstName": "Keith",
                    "lastName": "Doell",
                    "email": "random@example.com",
                    "linkedin": "linkedin.com/random_data",
                },
                {
                    "id": "unlocked-1",
                    "firstName": "Real",
                    "lastName": "Person",
                    "email": "real.person@example.com",
                    "linkedin": "linkedin.com/in/realperson",
                },
            ]
        }
    }
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with(payload)
    )

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["Owner"]))

    assert len(results) == 3
    locked_1, locked_2, unlocked = results

    assert locked_1.email is None
    assert locked_1.linkedin_url is None
    assert locked_1.first_name == "Lucy"

    assert locked_2.email is None
    assert locked_2.linkedin_url is None
    assert locked_2.first_name == "Keith"

    # A genuinely unlocked result must be unaffected
    assert unlocked.email == "real.person@example.com"
    assert unlocked.linkedin_url == "https://linkedin.com/in/realperson"


@pytest.mark.asyncio
async def test_reveal_requires_filter_id_from_raw_reference():
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with({})
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.reveal("lead-1", raw_reference={"id": "lead-1"})  # no _smartlead_filter_id

    with pytest.raises(ProviderUnavailableError):
        await provider.reveal("lead-1", raw_reference=None)


@pytest.mark.asyncio
async def test_reveal_calls_fetch_contacts_with_filter_id_and_maps_response():
    captured = {}

    def on_request(request):
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        import json

        captured["body"] = json.loads(request.content)

    payload = {
        "success": True,
        "data": {
            "list": [
                {
                    "id": "5a2ba2f8711eb336a3f213d8",
                    "firstName": "Adam",
                    "lastName": "Lewis",
                    "fullName": "Adam Lewis",
                    "title": "Vice President",
                    "company": {"name": "Marcus & Millichap"},
                    "department": ["Other"],
                    "level": "VP-Level",
                    "country": "United States",
                    "state": "Florida",
                    "city": "Venice",
                    "email": "adam.lewis@marcusmillichap.example",
                    "linkedin": "linkedin.com/in/adamlewis",
                    "status": "active",
                    "verificationStatus": "verified",
                    "catchAllStatus": "not_catch_all",
                }
            ],
        },
    }
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with(payload, on_request=on_request)
    )

    result = await provider.reveal(
        "5a2ba2f8711eb336a3f213d8", raw_reference={"_smartlead_filter_id": 7662385}
    )

    assert captured["path"] == "/api/v1/search-email-leads/fetch-contacts"
    assert captured["params"]["api_key"] == "test-key"
    assert captured["body"]["filter_id"] == 7662385
    assert captured["body"]["id"] == ["5a2ba2f8711eb336a3f213d8"]

    assert result is not None
    assert result["email"] == "adam.lewis@marcusmillichap.example"
    assert result["email_status"] == "verified"
    assert result["linkedin_url"] == "https://linkedin.com/in/adamlewis"
    assert result["city"] == "Venice"
    assert result["state"] == "Florida"
    assert result["seniority"] == "VP-Level"
    assert result["department"] == "Other"
    assert result["full_name"] == "Adam Lewis"


@pytest.mark.asyncio
async def test_reveal_returns_none_when_fetch_contacts_finds_nothing():
    payload = {"success": True, "data": {"list": []}}
    provider = SmartleadPersonDiscoveryProvider(
        api_key="test-key", client=_client_with({}), prospect_client=_prospect_client_with(payload)
    )

    result = await provider.reveal("missing-id", raw_reference={"_smartlead_filter_id": 123})

    assert result is None
