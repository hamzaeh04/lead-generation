from unittest.mock import AsyncMock
"""Phase 6: cost tracking/health instrumentation for provider calls."""
import pytest

from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory, ProviderMetadata

pytestmark = pytest.mark.asyncio


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
    headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}
    workspaces_response = await client.get("/api/v1/workspaces", headers=headers)
    return headers, workspaces_response.json()[0]["id"]


async def test_provider_usage_recorded_for_search_execute(client, db_session, unique_email, monkeypatch):
    from app.providers.base import DiscoveryCriteria, NormalizedCompany
    from app.providers.lead_sources.base import CompanyDiscoveryProvider

    class _StubProvider(CompanyDiscoveryProvider):
        name = "stub"
        category = ProviderCategory.COMPANY_DISCOVERY

        async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
            return [
                NormalizedCompany(
                    metadata=ProviderMetadata(provider="stub"), name="Acme Dental Group", domain="acmedental.example"
                )
            ]

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="stub", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubProvider()),
    )

    await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    health_response = await client.get("/api/v1/providers/health", headers=headers)
    health = {(row["provider"], row["category"]): row for row in health_response.json()}
    entry = health[("stub", "company_discovery")]
    assert entry["total_calls"] == 1
    assert entry["success_count"] == 1
    assert entry["success_rate"] == 1.0
    assert entry["last_success_at"] is not None


async def test_provider_health_and_usage_require_authentication(client):
    assert (await client.get("/api/v1/providers/usage")).status_code == 401
    assert (await client.get("/api/v1/providers/health")).status_code == 401
