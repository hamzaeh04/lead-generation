import pytest
from sqlalchemy import select

from app.models.provider_config import ProviderConfig
from app.models.user import User
from app.providers.base import ProviderCategory

pytestmark = pytest.mark.asyncio


async def _register(client, email):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Inc",
        },
    )
    return response.json()["access_token"]


async def _make_superuser(db_session, email):
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user.is_superuser = True
    await db_session.commit()
    return user


async def test_non_superuser_cannot_list_users(client, unique_email):
    token = await _register(client, unique_email)
    response = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_superuser_can_list_users_and_promote_another(client, db_session, unique_email):
    admin_token = await _register(client, unique_email)
    await _make_superuser(db_session, unique_email)

    other_email = f"other-{unique_email}"
    await _register(client, other_email)

    list_response = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert list_response.status_code == 200
    users = list_response.json()
    assert any(u["email"] == other_email for u in users)
    other_user_id = next(u["id"] for u in users if u["email"] == other_email)

    promote_response = await client.patch(
        f"/api/v1/admin/users/{other_user_id}/superuser",
        json={"is_superuser": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert promote_response.status_code == 200
    assert promote_response.json()["is_superuser"] is True


async def test_superuser_cannot_remove_own_superuser_access(client, db_session, unique_email):
    admin_token = await _register(client, unique_email)
    admin_user = await _make_superuser(db_session, unique_email)

    response = await client.patch(
        f"/api/v1/admin/users/{admin_user.id}/superuser",
        json={"is_superuser": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400


async def test_admin_provider_panel_merges_config_and_health(client, db_session, unique_email):
    provider_config = ProviderConfig(
        provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY, enabled=True,
        priority=1, monthly_free_quota=25,
    )
    db_session.add(provider_config)
    await db_session.commit()

    admin_token = await _register(client, unique_email)
    await _make_superuser(db_session, unique_email)

    response = await client.get(
        "/api/v1/admin/providers", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    rows = response.json()
    smartlead_row = next(r for r in rows if r["provider"] == "smartlead")
    assert smartlead_row["monthly_free_quota"] == 25
    assert smartlead_row["quota_remaining"] == 25
    assert smartlead_row["total_calls"] == 0


async def test_non_superuser_cannot_view_admin_provider_panel(client, unique_email):
    token = await _register(client, unique_email)
    response = await client.get(
        "/api/v1/admin/providers", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
