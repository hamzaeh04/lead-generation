from unittest.mock import AsyncMock
import uuid

import pytest

from app.models.contact import Contact

pytestmark = pytest.mark.asyncio


class _StubRevealProvider:
    def __init__(self, result: dict | None):
        self._result = result

    async def reveal(self, external_id: str, *, raw_reference: dict | None = None) -> dict | None:
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


async def test_reveal_enriches_contact_and_its_company(client, db_session, unique_email, monkeypatch):
    """Regression test: reveal() must not discard the rest of Apollo's
    response (location, seniority, email_status) or its nested
    organization data — that's real, provider-supplied enrichment, not
    just email/phone."""
    from app.models.company import Company

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    company = Company(workspace_id=uuid.UUID(workspace_id), name="BlackRock", domain="blackrock.com")
    db_session.add(company)
    await db_session.flush()

    contact = await _make_apollo_sourced_contact(db_session, workspace_id)
    contact.company_id = company.id
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubRevealProvider(
            {
                "first_name": "Larry",
                "last_name": "Fink",
                "full_name": "Larry Fink",
                "email": "larry@blackrock.example",
                "email_status": "verified",
                "phone": None,
                "linkedin_url": "http://www.linkedin.com/in/laurencefink",
                "city": "New York",
                "state": "New York",
                "country": "United States",
                "seniority": "c_suite",
                "department": "c_suite",
                "organization": {
                    "industry": "financial services",
                    "employee_count": 27000,
                    "annual_revenue": 24216000000.0,
                    "founded_year": 1988,
                    "website": "blackrock.com",
                    "phone": "+12125551000",
                    "linkedin_url": "http://www.linkedin.com/company/blackrock",
                    "city": "New York",
                    "state": "New York",
                    "country": "United States",
                },
            }
        )),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    contact_body = response.json()["contact"]
    assert contact_body["email_status"] == "verified"
    assert contact_body["linkedin_url"] == "http://www.linkedin.com/in/laurencefink"
    assert contact_body["city"] == "New York"
    assert contact_body["seniority"] == "c_suite"

    companies_response = await client.get(
        "/api/v1/companies", params={"workspace_id": workspace_id}, headers=headers
    )
    updated_company = next(c for c in companies_response.json() if c["id"] == str(company.id))
    assert updated_company["industry"] == "financial services"
    assert updated_company["employee_count"] == 27000
    assert updated_company["annual_revenue"] == 24216000000.0
    assert updated_company["founded_year"] == 1988


async def test_reveal_updates_contact_and_returns_revealed_true(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubRevealProvider(
            {"first_name": "Jordan", "last_name": "Alvarez", "full_name": "Jordan Alvarez", "email": "jordan@acme.example", "phone": "+15550100001"}
        )),
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
    # Phone is deliberately never stored from reveal, even though the
    # provider returned one — see LeadRevealService.reveal().
    assert body["contact"]["phone"] is None


async def test_reveal_works_for_smartlead_source_with_filter_id(
    client, db_session, unique_email, monkeypatch
):
    """End-to-end: Smartlead is now a revealable provider too (via the
    fetch-contacts unlock endpoint), not just Apollo."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    contact = Contact(workspace_id=uuid.UUID(workspace_id), first_name="Locked", full_name="Locked Lead")
    db_session.add(contact)
    await db_session.flush()
    from app.repositories.contact_repository import ContactRepository

    ContactRepository(db_session).add_source(
        contact=contact,
        provider="smartlead",
        external_id="smartlead-lead-1",
        source_url=None,
        source_type="api",
        raw_reference={"_smartlead_filter_id": 7662385},
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubRevealProvider(
            {
                "first_name": "Locked",
                "last_name": "Lead",
                "full_name": "Locked Lead",
                "email": "locked.lead@example.com",
                "email_status": "verified",
                "phone": None,
                "linkedin_url": "https://linkedin.com/in/lockedlead",
            }
        )),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revealed"] is True
    assert body["contact"]["email"] == "locked.lead@example.com"
    assert body["contact"]["email_status"] == "verified"
    assert body["contact"]["linkedin_url"] == "https://linkedin.com/in/lockedlead"


async def test_reveal_returns_revealed_false_when_provider_finds_nothing(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubRevealProvider(None)),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revealed"] is False
    assert body["contact"]["email"] is None  # unchanged, nothing fabricated
    # revealable must flip to false — retrying would spend another credit
    # for the same non-result
    assert body["contact"]["revealable"] is False


async def test_reveal_reports_false_when_only_a_non_email_field_is_found(
    client, db_session, unique_email, monkeypatch
):
    """Regression test: Apollo returning a bare last_name/phone with no
    email is not the success "revealed: true" implies to the UI (which
    shows "Details revealed" and would otherwise keep the button up,
    inviting repeat credit spend for the same non-result)."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubRevealProvider(
            {"first_name": None, "last_name": "Alvarez", "full_name": None, "email": None, "phone": None}
        )),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revealed"] is False
    assert body["contact"]["last_name"] == "Alvarez"  # still applied
    assert body["contact"]["email"] is None
    assert body["contact"]["revealable"] is False


async def test_reveal_refuses_second_attempt_after_first_found_no_email(
    client, db_session, unique_email, monkeypatch
):
    """Regression test for the actual bug: this contact was reveal-clicked
    6+ times in a row in production because the button never disabled,
    each one a separate billed Apollo call for the identical non-result.
    A second attempt must be refused outright, not silently re-billed."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)

    call_count = 0

    async def build_provider(provider_name, category, settings, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _StubRevealProvider(None)

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace", build_provider
    )

    first = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )
    assert first.status_code == 200
    assert call_count == 1

    second = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )
    assert second.status_code == 409
    assert call_count == 1  # provider must NOT have been called again


async def test_reveal_skips_provider_when_email_already_known(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)
    contact.email = "already@known.example"
    await db_session.commit()

    called = False

    async def build_provider(provider_name, category, settings, *args, **kwargs):
        nonlocal called
        called = True
        return _StubRevealProvider({"email": "should-not-be-used@example.com"})

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace", build_provider
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/reveal", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["contact"]["email"] == "already@known.example"
    assert called is False


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


async def test_get_lead_revealable_true_for_smartlead_with_filter_id(client, db_session, unique_email):
    """A Smartlead-sourced contact IS revealable once its source carries
    the filter_id its unlock call needs (captured at search time for any
    result found after this feature shipped)."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    contact = Contact(workspace_id=uuid.UUID(workspace_id), first_name="Locked", full_name="Locked Lead")
    db_session.add(contact)
    await db_session.flush()
    from app.repositories.contact_repository import ContactRepository

    ContactRepository(db_session).add_source(
        contact=contact,
        provider="smartlead",
        external_id="smartlead-lead-1",
        source_url=None,
        source_type="api",
        raw_reference={"_smartlead_filter_id": 7662385},
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.json()["revealable"] is True


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


async def test_reveal_returns_503_when_apollo_credentials_missing(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_apollo_sourced_contact(db_session, workspace_id)
    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=None),
    )

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
