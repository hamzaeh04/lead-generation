from unittest.mock import AsyncMock
import pytest

from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory

pytestmark = pytest.mark.asyncio


async def _register(client, unique_email):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Agency",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_provider_health_reports_quota_remaining(client, db_session, unique_email, monkeypatch):
    from app.providers.base import NormalizedCompany, ProviderMetadata
    from app.providers.lead_sources.base import CompanyDiscoveryProvider

    class _StubProvider(CompanyDiscoveryProvider):
        name = "stub"
        category = ProviderCategory.COMPANY_DISCOVERY

        async def discover_companies(self, criteria):
            return [NormalizedCompany(metadata=ProviderMetadata(provider="stub"), name="Acme")]

    headers = await _register(client, unique_email)
    workspace_id = (await client.get("/api/v1/workspaces", headers=headers)).json()[0]["id"]

    db_session.add(
        ProviderConfig(
            provider="stub",
            category=ProviderCategory.COMPANY_DISCOVERY,
            enabled=True,
            priority=1,
            monthly_free_quota=25,
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubProvider()),
    )

    for _ in range(3):
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
    entry = next(r for r in health_response.json() if r["provider"] == "stub")

    assert entry["calls_this_month"] == 3
    assert entry["monthly_free_quota"] == 25
    assert entry["quota_remaining"] == 22


async def test_provider_health_quota_remaining_null_when_no_quota_set(client, db_session, unique_email):
    headers = await _register(client, unique_email)

    db_session.add(
        ProviderConfig(provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    health_response = await client.get("/api/v1/providers/health", headers=headers)
    assert health_response.status_code == 200
    # No usage rows yet for this provider/category -> not present in health_summary at all
    assert not any(r["provider"] == "smartlead" for r in health_response.json())


async def test_update_provider_can_set_monthly_free_quota(client, db_session, unique_email):
    from sqlalchemy import select

    from app.models.user import User

    headers = await _register(client, unique_email)
    provider_config = ProviderConfig(
        provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY, enabled=False, priority=1
    )
    db_session.add(provider_config)
    await db_session.commit()

    user = (await db_session.execute(select(User))).scalars().first()
    user.is_superuser = True
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/providers/{provider_config.id}",
        json={"monthly_free_quota": 25},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["monthly_free_quota"] == 25
