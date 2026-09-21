import uuid

import pytest

from app.models.contact import Contact

pytestmark = pytest.mark.asyncio


class _StubRevealProvider:
    def __init__(self, result: dict | None):
        self._result = result

    async def reveal(self, external_id: str) -> dict | None:
        return self._result


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


async def _make_apollo_sourced_contact(db_session, workspace_id, *, external_id="apollo-person-1"):
    contact = Contact(
        workspace_id=uuid.UUID(workspace_id),
        first_name="Jordan",
        full_name="Jordan",
        job_title="Owner",
    )
    db_session.add(contact)
    await db_session.flush()

    from app.repositories.contact_repository import ContactRepository

    ContactRepository(db_session).add_source(
        contact=contact,
        provider="apollo",
        external_id=external_id,
        source_url=None,
        source_type="api",
        raw_reference={"id": external_id},
    )
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


async def test_reveal_updates_contact_and_returns_revealed_true(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubRevealProvider(
            {"first_name": "Jordan", "last_name": "Alvarez", "full_name": "Jordan Alvarez", "email": "jordan@acme.example", "phone": "+15550100001"}
        ),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revealed"] is True
    assert body["contact"]["email"] == "jordan@acme.example"
    assert body["contact"]["last_name"] == "Alvarez"
    assert body["contact"]["full_name"] == "Jordan Alvarez"
    assert body["contact"]["phone"] == "+15550100001"


async def test_reveal_returns_revealed_false_when_provider_finds_nothing(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubRevealProvider(None),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revealed"] is False
    assert body["contact"]["email"] is None  # unchanged, nothing fabricated


async def test_get_lead_revealable_reflects_source_provider(client, db_session, unique_email):
    """Regression test: the "Reveal" button must never appear for a
    contact whose only source is a provider with no on-demand unlock
    (e.g. Smartlead) — GET /leads/{id} is what the UI reads `revealable`
    from, and it must reflect the real source, not just default true."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    apollo_contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    smartlead_contact = Contact(
        workspace_id=uuid.UUID(workspace_id), first_name="Locked", full_name="Locked Lead"
    )
    db_session.add(smartlead_contact)
    await db_session.flush()
    from app.repositories.contact_repository import ContactRepository

    ContactRepository(db_session).add_source(
        contact=smartlead_contact,
        provider="smartlead",
        external_id="smartlead-lead-1",
        source_url=None,
        source_type="api",
        raw_reference={},
    )
    await db_session.commit()

    apollo_response = await client.get(
        f"/api/v1/leads/{apollo_contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    smartlead_response = await client.get(
        f"/api/v1/leads/{smartlead_contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )

    assert apollo_response.json()["revealable"] is True
    assert smartlead_response.json()["revealable"] is False


async def test_reveal_404_when_contact_has_no_revealable_source(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = Contact(workspace_id=uuid.UUID(workspace_id), first_name="No", full_name="No Source")
    db_session.add(contact)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 404


async def test_reveal_404_when_contact_does_not_exist(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        f"/api/v1/leads/{uuid.uuid4()}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 404


async def test_reveal_returns_503_when_apollo_credentials_missing(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)
    # APOLLO_API_KEY is unset in the test environment, so build_provider
    # (unpatched, real factory) returns None here.

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 503
    assert "APOLLO_API_KEY" in response.json()["detail"]


async def test_reveal_requires_editor_role(client, db_session, unique_email):
    owner_headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    viewer_email = f"viewer-{unique_email}"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": viewer_email,
            "password": "S3curePassw0rd!",
            "full_name": "Viewer User",
            "workspace_name": "Ignored Co",
        },
    )
    add_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": viewer_email, "role": "viewer"},
        headers=owner_headers,
    )
    assert add_response.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": viewer_email, "password": "S3curePassw0rd!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=viewer_headers
    )

    assert response.status_code == 403


async def test_reveal_requires_authentication(client, unique_email):
    response = await client.post(
        f"/api/v1/leads/{uuid.uuid4()}/reveal", params={"workspace_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401
