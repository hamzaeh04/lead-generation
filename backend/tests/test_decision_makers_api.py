from unittest.mock import AsyncMock
import uuid

import pytest

from app.models.company import Company
from app.models.provider_config import ProviderConfig
from app.providers.base import NormalizedContact, ProviderCategory, ProviderMetadata, ProviderUnavailableError
from app.providers.people_sources.base import PersonDiscoveryProvider

pytestmark = pytest.mark.asyncio


class _StubDecisionMakerProvider(PersonDiscoveryProvider):
    name = "stub"
    category = ProviderCategory.PERSON_DISCOVERY

    async def discover_people(self, criteria):
        raise NotImplementedError

    async def discover_decision_makers(self, company_domain, target_titles):
        return [
            NormalizedContact(
                metadata=ProviderMetadata(provider="stub", external_id="p-1", source_type="api"),
                first_name="Jordan",
                last_name="Alvarez",
                full_name="Jordan Alvarez",
                job_title="Owner",
                email="jordan@acmedental.example",
                company_domain=company_domain,
            )
        ]


class _EmptyDecisionMakerProvider(PersonDiscoveryProvider):
    name = "stub-empty"
    category = ProviderCategory.PERSON_DISCOVERY

    async def discover_people(self, criteria):
        raise NotImplementedError

    async def discover_decision_makers(self, company_domain, target_titles):
        return []


class _FailingDecisionMakerProvider(PersonDiscoveryProvider):
    name = "stub-fail"
    category = ProviderCategory.PERSON_DISCOVERY

    async def discover_people(self, criteria):
        raise NotImplementedError

    async def discover_decision_makers(self, company_domain, target_titles):
        raise ProviderUnavailableError("stub-fail: simulated outage")


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


async def _make_company(db_session, workspace_id, *, domain="acmedental.example"):
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group", domain=domain)
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


async def test_decision_makers_persists_and_returns_contact(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="stub", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.decision_maker_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubDecisionMakerProvider()),
    )

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={"target_titles": ["owner"]},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contacts_created"] == 1
    assert body["contacts_matched"] == 0
    assert body["contacts"][0]["full_name"] == "Jordan Alvarez"
    assert body["contacts"][0]["job_title"] == "Owner"
    assert body["contacts"][0]["email"] == "jordan@acmedental.example"
    assert body["contacts"][0]["company_id"] == str(company.id)


async def test_decision_makers_requires_company_domain(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = Company(workspace_id=uuid.UUID(workspace_id), name="No Domain Co", domain=None)
    db_session.add(company)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    assert "domain" in response.json()["detail"].lower()


async def test_decision_makers_404s_for_missing_company(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    response = await client.post(
        f"/api/v1/companies/{uuid.uuid4()}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=headers,
    )
    assert response.status_code == 404


async def test_decision_makers_no_enabled_provider_returns_400(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    assert "no person-discovery provider" in response.json()["detail"].lower()


async def test_decision_makers_missing_credentials_returns_503(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="apollo", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.decision_maker_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=None),
    )

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=headers,
    )
    assert response.status_code == 503
    assert "apollo" in response.json()["detail"].lower()


async def test_decision_makers_falls_back_to_next_provider_after_failure(
    client, db_session, unique_email, monkeypatch
):
    """Regression-shaped test mirroring the email-discovery waterfall bug
    (see app/services/email_discovery_service.py comment): a failing
    provider must not stop the waterfall, and must be logged as a real
    failure in the usage log — not silently swallowed as success."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="stub-fail", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    db_session.add(
        ProviderConfig(provider="stub", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=2)
    )
    await db_session.commit()

    providers = {"stub-fail": _FailingDecisionMakerProvider(), "stub": _StubDecisionMakerProvider()}

    async def _build(session, workspace_id, provider_name, category, settings):
        return providers[provider_name]

    monkeypatch.setattr(
        "app.services.decision_maker_service.provider_factory.build_provider_for_workspace",
        _build,
    )

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contacts_created"] == 1

    usage_response = await client.get(
        "/api/v1/providers/usage", params={"provider": "stub-fail"}, headers=headers
    )
    usage_rows = usage_response.json()
    assert len(usage_rows) == 1
    assert usage_rows[0]["success"] is False


async def test_decision_makers_empty_result_is_not_an_error(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="stub-empty", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.decision_maker_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_EmptyDecisionMakerProvider()),
    )

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"contacts_created": 0, "contacts_matched": 0, "contacts": []}


async def test_decision_makers_requires_workspace_editor_role(client, db_session, unique_email):
    """Viewer role should be rejected — this endpoint creates data."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

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
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": viewer_email, "role": "viewer"},
        headers=headers,
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": viewer_email, "password": "S3curePassw0rd!"}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(
        f"/api/v1/companies/{company.id}/decision-makers",
        params={"workspace_id": workspace_id},
        json={},
        headers=viewer_headers,
    )
    assert response.status_code == 403
