import json

import pytest

from app.models.provider_config import ProviderConfig
from app.providers.ai.base import AIGenerationRequest, AIGenerationResult
from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.lead_sources.base import CompanyDiscoveryProvider

pytestmark = pytest.mark.asyncio


class _StubAIProvider:
    def __init__(self, response: dict):
        self._response = response

    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        return AIGenerationResult(
            text=json.dumps(self._response),
            model="stub-model",
            prompt_version=request.prompt_version,
            source_fields_used=list(request.source_fields.keys()),
        )


class _FailingAIProvider:
    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        raise ProviderUnavailableError("groq: simulated outage")


class _StubCompanyDiscoveryProvider(CompanyDiscoveryProvider):
    name = "stub"
    category = ProviderCategory.COMPANY_DISCOVERY

    async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        return [
            NormalizedCompany(
                metadata=ProviderMetadata(provider="stub", external_id="stub-1"),
                name="Acme Dental Group",
                domain="acmedental.example",
                city="Miami",
                state="FL",
            )
        ]


async def _register_and_get_workspace(client, unique_email):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Agency",
        },
    )
    access_token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    workspaces_response = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces_response.json()[0]["id"]
    return headers, workspace_id


async def test_search_execute_with_stub_provider_persists_results(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="stub", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubCompanyDiscoveryProvider(),
    )

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {"industry": "dental", "state": "FL"},
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["companies_created"] == 1
    assert len(body["companies"]) == 1
    assert body["companies"][0]["name"] == "Acme Dental Group"

    companies_response = await client.get(
        "/api/v1/companies", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(companies_response.json()) == 1


async def test_search_execute_matched_company_serializes_correctly(
    client, db_session, unique_email, monkeypatch
):
    """Regression test: a matched (not newly-created) company is mutated
    in-place by the resolver, then returned in the API response. Before the
    post-commit refresh fix, serializing it crashed with MissingGreenlet
    because onupdate=func.now() columns are expired after commit."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="stub", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubCompanyDiscoveryProvider(),
    )

    payload = {
        "workspace_id": workspace_id,
        "provider": "stub",
        "category": "company_discovery",
        "criteria": {"industry": "dental", "state": "FL"},
    }
    first = await client.post("/api/v1/search/execute", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["companies_created"] == 1

    second = await client.post("/api/v1/search/execute", json=payload, headers=headers)
    assert second.status_code == 200
    body = second.json()
    assert body["companies_matched"] == 1
    assert body["companies_created"] == 0
    assert body["companies"][0]["name"] == "Acme Dental Group"


async def test_search_execute_rejects_disabled_provider(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apollo",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"]


async def test_search_execute_reports_missing_credentials(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="apollo", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    # APOLLO_API_KEY is not set in the test environment, so the registry
    # allows it but the factory can't build a working provider instance.
    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apollo",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 503
    assert "APOLLO_API_KEY" in response.json()["detail"]


async def test_search_execute_requires_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000000",
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 403


async def test_search_execute_requires_authentication(client):
    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000000",
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {},
        },
    )
    assert response.status_code == 401


async def test_parse_prompt_splits_known_fields_from_extra_filters(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()

    ai_response = {
        "job_titles": ["VP of Sales", "Head of Sales"],
        "city": "Austin",
        "employee_count_min": 50,
        "employee_count_max": 200,
        "technologies": ["salesforce"],  # not a top-level DiscoveryCriteria field -> extra_filters
        "department": ["Sales"],  # smartlead-only field -> extra_filters
    }
    monkeypatch.setattr(
        "app.services.prospect_prompt_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubAIProvider(ai_response),
    )

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": workspace_id, "provider": "apollo", "prompt": "VPs of sales in Austin using Salesforce"},
        headers=headers,
    )

    assert response.status_code == 200
    criteria = response.json()["criteria"]
    assert criteria["job_titles"] == ["VP of Sales", "Head of Sales"]
    assert criteria["city"] == "Austin"
    assert criteria["employee_count_min"] == 50
    assert criteria["employee_count_max"] == 200
    assert criteria["extra_filters"] == {"technologies": ["salesforce"], "department": ["Sales"]}


async def test_parse_prompt_never_invents_fields_the_ai_omitted(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.prospect_prompt_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubAIProvider({"job_titles": ["Founder"]}),
    )

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": workspace_id, "provider": "apollo", "prompt": "founders"},
        headers=headers,
    )

    criteria = response.json()["criteria"]
    assert criteria["job_titles"] == ["Founder"]
    assert criteria["city"] is None
    assert criteria["state"] is None
    assert criteria["domain"] is None
    assert criteria["extra_filters"] == {}


async def test_parse_prompt_rejects_unknown_provider(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": workspace_id, "provider": "serpapi", "prompt": "anything"},
        headers=headers,
    )

    assert response.status_code == 400


async def test_parse_prompt_returns_502_when_ai_output_is_invalid(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()

    # employee_count_min must be an int — the AI hallucinated a string.
    monkeypatch.setattr(
        "app.services.prospect_prompt_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubAIProvider({"employee_count_min": "a lot"}),
    )

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": workspace_id, "provider": "apollo", "prompt": "big companies"},
        headers=headers,
    )

    assert response.status_code == 502


async def test_parse_prompt_returns_503_when_no_ai_provider_has_credentials(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()
    # GROQ_API_KEY is unset in the test environment, so the registry allows
    # it but the factory can't build a working provider instance.

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": workspace_id, "provider": "apollo", "prompt": "founders"},
        headers=headers,
    )

    assert response.status_code == 503


async def test_parse_prompt_requires_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000000",
            "provider": "apollo",
            "prompt": "founders",
        },
        headers=headers,
    )

    assert response.status_code == 403


async def test_parse_prompt_returns_502_when_ai_provider_errors(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.prospect_prompt_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _FailingAIProvider(),
    )

    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": workspace_id, "provider": "apollo", "prompt": "founders"},
        headers=headers,
    )

    assert response.status_code == 502


async def test_parse_prompt_requires_authentication(client):
    response = await client.post(
        "/api/v1/search/parse-prompt",
        json={"workspace_id": "00000000-0000-0000-0000-000000000000", "provider": "apollo", "prompt": "founders"},
    )
    assert response.status_code == 401
