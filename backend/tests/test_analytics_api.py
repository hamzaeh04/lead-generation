import uuid
from datetime import datetime, timezone

import pytest

from app.models.company import Company, CompanySource
from app.models.contact import Contact, LeadStatus
from app.models.intent_signal import IntentSignal, IntentSignalType
from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory, ProviderMetadata
from app.providers.email_senders.base import OutboundEmail, SendResult, SendStatus

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


async def test_analytics_overview_counts_companies_and_contacts(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group")
    db_session.add(company)
    await db_session.flush()
    db_session.add(CompanySource(company_id=company.id, provider="apollo", source_type="api"))
    contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, email="jordan@acmedental.example")
    db_session.add(contact)
    await db_session.commit()

    response = await client.get(
        "/api/v1/analytics/overview", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_companies"] == 1
    assert body["total_contacts"] == 1
    assert body["positive_reply_rate"] is None  # never fabricated — no sentiment classification exists
    assert body["top_sources"] == [{"provider": "apollo", "count": 1}]
    assert body["verified_emails"] == 1  # no verification provider wired up — counts contacts with an email


async def test_analytics_overview_counts_high_intent_companies(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group")
    db_session.add(company)
    await db_session.flush()
    # SERVICE_REQUEST (30) + FUNDING (20) = 50, meeting the dashboard's
    # high-intent threshold. A single SERVICE_REQUEST alone (30) would not.
    for signal_type in (IntentSignalType.SERVICE_REQUEST, IntentSignalType.FUNDING):
        db_session.add(
            IntentSignal(
                workspace_id=uuid.UUID(workspace_id), company_id=company.id,
                signal_type=signal_type, provider="manual", source="reddit",
                source_url="https://reddit.com/x", detected_at=datetime.now(timezone.utc),
            )
        )
    await db_session.commit()

    response = await client.get(
        "/api/v1/analytics/overview", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.json()["high_intent_leads"] == 1


async def test_analytics_overview_meetings_and_conversions(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = Contact(workspace_id=uuid.UUID(workspace_id), email="a@example.com", status=LeadStatus.MEETING)
    db_session.add(contact)
    contact2 = Contact(workspace_id=uuid.UUID(workspace_id), email="b@example.com", status=LeadStatus.WON)
    db_session.add(contact2)
    await db_session.commit()

    response = await client.get(
        "/api/v1/analytics/overview", params={"workspace_id": workspace_id}, headers=headers
    )
    body = response.json()
    assert body["meetings"] == 1
    assert body["conversions"] == 1


async def test_analytics_overview_requires_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)
    response = await client.get(
        "/api/v1/analytics/overview",
        params={"workspace_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 403


class _StubSender:
    async def send(self, message: OutboundEmail) -> SendResult:
        return SendResult(status=SendStatus.SENT, provider_message_id="stub-id")


async def test_campaign_report_computed_from_real_events(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = Contact(workspace_id=uuid.UUID(workspace_id), email="jordan@acmedental.example")
    db_session.add(contact)
    await db_session.commit()

    campaign_response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": "Q1 Outreach", "from_email": "agency@example.com"},
        headers=headers,
    )
    campaign_id = campaign_response.json()["id"]
    await client.post(
        f"/api/v1/campaigns/{campaign_id}/steps",
        params={"workspace_id": workspace_id},
        json={"step_number": 1, "subject": "Hi", "body": "Hello. {{unsubscribe_url}}"},
        headers=headers,
    )
    await client.post(f"/api/v1/campaigns/{campaign_id}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign_id}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )

    db_session.add(
        ProviderConfig(provider="stub", category=ProviderCategory.EMAIL_SENDER, enabled=True, priority=1)
    )
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.campaign_sending_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubSender(),
    )
    await client.post(
        f"/api/v1/campaigns/{campaign_id}/process", params={"workspace_id": workspace_id}, headers=headers
    )

    report_response = await client.get(
        f"/api/v1/campaigns/{campaign_id}/report", params={"workspace_id": workspace_id}, headers=headers
    )

    assert report_response.status_code == 200
    body = report_response.json()
    assert body["contacts_enrolled"] == 1
    assert body["sent"] == 1
    assert body["delivered"] == 1
    assert body["bounce_rate"] == 0.0
    assert body["name"] == "Q1 Outreach"


async def test_campaign_report_404_for_missing_campaign(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    response = await client.get(
        f"/api/v1/campaigns/{uuid.uuid4()}/report", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 404
