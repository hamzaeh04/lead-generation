"""Verifies the automatic CRM status transitions wired into existing
services (campaign send -> CONTACTED, webhook events ->
OPENED/CLICKED/REPLIED/BOUNCED/UNSUBSCRIBED)."""
import uuid

import pytest
from sqlalchemy import select

from app.models.campaign_recipient import CampaignRecipient
from app.models.company import Company
from app.models.contact import Contact
from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory
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


async def _make_contact(db_session, workspace_id, *, email="jordan@acmedental.example"):
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group")
    db_session.add(company)
    await db_session.flush()
    contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, email=email)
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


class _StubSender:
    async def send(self, message: OutboundEmail) -> SendResult:
        return SendResult(status=SendStatus.SENT, provider_message_id="stub-id")


async def test_successful_send_bumps_status_to_contacted(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    campaign_response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": "Q1", "from_email": "agency@example.com"},
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

    lead_response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.json()["status"] == "contacted"


async def test_webhook_bounce_updates_contact_status(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    campaign_response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": "Q1", "from_email": "agency@example.com"},
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

    await client.post(
        "/api/v1/webhooks/email-events",
        json={"workspace_id": workspace_id, "contact_email": contact.email, "event_type": "bounced"},
    )

    lead_response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.json()["status"] == "bounced"


async def _send_one_campaign_step(client, db_session, monkeypatch, headers, workspace_id, contact):
    campaign_response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": "Q1", "from_email": "agency@example.com"},
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

    result = await db_session.execute(
        select(CampaignRecipient).where(CampaignRecipient.contact_id == contact.id)
    )
    return result.scalar_one()


async def test_open_tracking_pixel_returns_image_regardless_of_token(client):
    # Unknown/malformed recipient id must never break the pixel — a broken
    # image icon in the recipient's inbox would be a giveaway that
    # something's wrong, so this always returns real pixel bytes.
    response = await client.get(f"/api/v1/track/open/{uuid.uuid4()}.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/gif"
    assert len(response.content) > 0


async def test_open_tracking_pixel_upgrades_recipient_and_lead_status(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    recipient = await _send_one_campaign_step(client, db_session, monkeypatch, headers, workspace_id, contact)

    # Before the pixel fires: sent (one tick), not yet opened.
    lead_response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.json()["status"] == "contacted"
    assert lead_response.json()["email_track_status"] == "sent"

    pixel_response = await client.get(f"/api/v1/track/open/{recipient.id}.png")
    assert pixel_response.status_code == 200

    lead_response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.json()["status"] == "opened"
    assert lead_response.json()["email_track_status"] == "opened"


async def test_open_tracking_pixel_never_downgrades_a_further_along_status(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    recipient = await _send_one_campaign_step(client, db_session, monkeypatch, headers, workspace_id, contact)

    await client.post(
        "/api/v1/webhooks/email-events",
        json={"workspace_id": workspace_id, "contact_email": contact.email, "event_type": "replied"},
    )

    await client.get(f"/api/v1/track/open/{recipient.id}.png")

    lead_response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.json()["status"] == "replied"
