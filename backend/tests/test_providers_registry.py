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
    return response.json()["access_token"]


async def test_list_providers_requires_authentication(client):
    response = await client.get("/api/v1/providers")
    assert response.status_code == 401


async def test_list_providers_returns_seeded_registry(client, db_session, unique_email):
    db_session.add(
        ProviderConfig(
            provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY, enabled=False, priority=1
        )
    )
    await db_session.commit()

    access_token = await _register(client, unique_email)
    response = await client.get(
        "/api/v1/providers", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    providers = response.json()
    assert any(p["provider"] == "smartlead" and p["category"] == "person_discovery" for p in providers)


async def test_non_superuser_cannot_update_provider(client, db_session, unique_email):
    provider_config = ProviderConfig(
        provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY, enabled=False, priority=1
    )
    db_session.add(provider_config)
    await db_session.commit()

    access_token = await _register(client, unique_email)
    response = await client.patch(
        f"/api/v1/providers/{provider_config.id}",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403


async def test_superuser_can_toggle_provider(client, db_session, unique_email):
    from sqlalchemy import select

    from app.models.user import User

    provider_config = ProviderConfig(
        provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY, enabled=False, priority=1
    )
    db_session.add(provider_config)
    await db_session.commit()

    access_token = await _register(client, unique_email)

    user = (
        await db_session.execute(select(User).where(User.email == unique_email))
    ).scalar_one()
    user.is_superuser = True
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/providers/{provider_config.id}",
        json={"enabled": True, "priority": 5},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["priority"] == 5
