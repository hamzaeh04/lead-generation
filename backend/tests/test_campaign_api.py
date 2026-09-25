import uuid

import pytest

from app.models.company import Company
from app.models.contact import Contact
from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory
from app.providers.email_senders.base import OutboundEmail, SendResult, SendStatus

pytestmark = pytest.mark.asyncio


class _StubSender:
    def __init__(self):
        self.sent: list[OutboundEmail] = []

    async def send(self, message: OutboundEmail) -> SendResult:
        self.sent.append(message)
        return SendResult(status=SendStatus.SENT, provider_message_id="stub-id")


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
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group", city="Miami")
    db_session.add(company)
    await db_session.flush()
    contact = Contact(
        workspace_id=uuid.UUID(workspace_id), company_id=company.id,
        first_name="Jordan", email=email,
    )
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


async def _create_campaign(client, headers, workspace_id, *, daily_limit=50):
    response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": "Q1 Outreach", "from_email": "agency@example.com", "daily_limit": daily_limit},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def _add_step(client, headers, workspace_id, campaign_id, *, step_number=1, delay_days=0):
    response = await client.post(
        f"/api/v1/campaigns/{campaign_id}/steps",
        params={"workspace_id": workspace_id},
        json={
            "step_number": step_number,
            "delay_days": delay_days,
            "subject": "Hi {{first_name}}",
            "body": "Hello {{first_name}} from {{company_name}}. Unsubscribe: {{unsubscribe_url}}",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def _enable_stub_sender(db_session, monkeypatch):
    db_session.add(
        ProviderConfig(provider="stub", category=ProviderCategory.EMAIL_SENDER, enabled=True, priority=1)
    )
    await db_session.commit()
    stub = _StubSender()
    monkeypatch.setattr(
        "app.services.campaign_sending_service.provider_factory.build_provider",
        lambda provider_name, category, settings: stub,
    )
    return stub


async def test_full_campaign_lifecycle_sends_and_completes(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])

    start_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    enroll_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )
    assert enroll_response.json()["enrolled"] == 1

    stub = await _enable_stub_sender(db_session, monkeypatch)

    process_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )
    assert process_response.status_code == 200
    body = process_response.json()
    assert body["sent"] == 1
    assert body["completed"] == 1  # single-step campaign completes immediately after sending

    assert len(stub.sent) == 1
    assert stub.sent[0].to_email == "jordan@acmedental.example"
    assert "Hello Jordan from Acme Dental Group" in stub.sent[0].html_body


async def test_send_embeds_open_tracking_pixel_when_public_base_url_configured(
    client, db_session, unique_email, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "PUBLIC_BASE_URL", "https://example.test")

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )

    stub = await _enable_stub_sender(db_session, monkeypatch)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )

    assert len(stub.sent) == 1
    assert "https://example.test/api/v1/track/open/" in stub.sent[0].html_body
    assert stub.sent[0].html_body.rstrip().endswith('.png" width="1" height="1" alt="" style="display:none" />')


async def test_send_skips_tracking_pixel_when_public_base_url_unset(
    client, db_session, unique_email, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "PUBLIC_BASE_URL", None)

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )

    stub = await _enable_stub_sender(db_session, monkeypatch)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )

    assert len(stub.sent) == 1
    assert "/track/open/" not in stub.sent[0].html_body


async def test_starting_campaign_without_steps_fails(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    campaign = await _create_campaign(client, headers, workspace_id)

    response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 400


async def test_suppressed_contact_is_never_sent_to(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])

    await client.post(
        "/api/v1/suppressions",
        params={"workspace_id": workspace_id},
        json={"email": contact.email, "reason": "manual"},
        headers=headers,
    )

    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )

    stub = await _enable_stub_sender(db_session, monkeypatch)

    process_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )

    assert process_response.json()["suppressed"] == 1
    assert process_response.json()["sent"] == 0
    assert len(stub.sent) == 0


async def test_unsubscribe_endpoint_creates_suppression_and_blocks_future_sends(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )

    from app.services.unsubscribe_token_service import create_unsubscribe_token

    token = create_unsubscribe_token(workspace_id=uuid.UUID(workspace_id), contact_id=contact.id)
    unsubscribe_response = await client.get(f"/unsubscribe/{token}")
    assert unsubscribe_response.status_code == 200

    suppressions_response = await client.get(
        "/api/v1/suppressions", params={"workspace_id": workspace_id}, headers=headers
    )
    assert any(s["email"] == contact.email for s in suppressions_response.json())

    stub = await _enable_stub_sender(db_session, monkeypatch)
    process_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )
    assert process_response.json()["suppressed"] == 1
    assert len(stub.sent) == 0


async def test_unsubscribe_with_invalid_token_returns_400(client):
    response = await client.get("/unsubscribe/garbage-token")
    assert response.status_code == 400


async def test_daily_limit_caps_sends_per_run(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact_a = await _make_contact(db_session, workspace_id, email="a@acmedental.example")
    contact_b = await _make_contact(db_session, workspace_id, email="b@acmedental.example")
    campaign = await _create_campaign(client, headers, workspace_id, daily_limit=1)
    await _add_step(client, headers, workspace_id, campaign["id"])
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact_a.id), str(contact_b.id)]},
        headers=headers,
    )

    stub = await _enable_stub_sender(db_session, monkeypatch)

    process_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )

    assert process_response.json()["sent"] == 1
    assert len(stub.sent) == 1

    # A second immediate run should not send more — quota exhausted for today.
    second_response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )
    assert second_response.json()["skipped_no_quota"] is True
    assert len(stub.sent) == 1


async def test_multi_step_sequence_schedules_next_step_with_delay(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"], step_number=1, delay_days=0)
    await _add_step(client, headers, workspace_id, campaign["id"], step_number=2, delay_days=3)
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )

    stub = await _enable_stub_sender(db_session, monkeypatch)

    first_run = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )
    assert first_run.json()["sent"] == 1
    assert first_run.json()["completed"] == 0  # step 2 still pending, not done yet

    # Step 2 isn't due yet (3-day delay) — a second run right away sends nothing new.
    second_run = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )
    assert second_run.json()["sent"] == 0
    assert len(stub.sent) == 1


async def test_preview_renders_variables_without_sending(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])

    response = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/preview",
        params={"workspace_id": workspace_id},
        json={"contact_id": str(contact.id), "step_number": 1},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "Jordan" in body["subject"]
    assert "Acme Dental Group" in body["body"]
    assert "first_name" in body["variables_filled"]


async def test_webhook_bounce_creates_suppression_and_updates_recipient(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"])
    await client.post(f"/api/v1/campaigns/{campaign['id']}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/enroll",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact.id)]},
        headers=headers,
    )
    await _enable_stub_sender(db_session, monkeypatch)
    await client.post(
        f"/api/v1/campaigns/{campaign['id']}/process", params={"workspace_id": workspace_id}, headers=headers
    )

    webhook_response = await client.post(
        "/api/v1/webhooks/email-events",
        json={"workspace_id": workspace_id, "contact_email": contact.email, "event_type": "bounced"},
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["suppressed"] is True

    suppressions_response = await client.get(
        "/api/v1/suppressions", params={"workspace_id": workspace_id}, headers=headers
    )
    assert any(
        s["email"] == contact.email and s["reason"] == "bounce" for s in suppressions_response.json()
    )


async def test_campaign_endpoints_require_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)
    other_workspace_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        "/api/v1/campaigns", params={"workspace_id": other_workspace_id}, headers=headers
    )
    assert response.status_code == 403


async def test_campaign_endpoints_require_authentication(client):
    response = await client.get(
        "/api/v1/campaigns", params={"workspace_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401


async def test_update_campaign_step_edits_fields(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    campaign = await _create_campaign(client, headers, workspace_id)
    step = await _add_step(client, headers, workspace_id, campaign["id"])

    response = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}/steps/{step['id']}",
        params={"workspace_id": workspace_id},
        json={"subject": "New subject", "delay_days": 3},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "New subject"
    assert body["delay_days"] == 3
    assert body["body"] == step["body"]  # untouched fields stay as-is


async def test_update_campaign_step_number_conflict_returns_409(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    campaign = await _create_campaign(client, headers, workspace_id)
    await _add_step(client, headers, workspace_id, campaign["id"], step_number=1)
    step_two = await _add_step(client, headers, workspace_id, campaign["id"], step_number=2)

    response = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}/steps/{step_two['id']}",
        params={"workspace_id": workspace_id},
        json={"step_number": 1},
        headers=headers,
    )
    assert response.status_code == 409


async def test_swapping_step_numbers_reorders_steps(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    campaign = await _create_campaign(client, headers, workspace_id)
    step_one = await _add_step(client, headers, workspace_id, campaign["id"], step_number=1, delay_days=0)
    step_two = await _add_step(client, headers, workspace_id, campaign["id"], step_number=2, delay_days=3)

    # Moving step 2 up: give it a temporary out-of-range number first so the
    # two swaps never collide with an existing step_number mid-flight.
    await client.patch(
        f"/api/v1/campaigns/{campaign['id']}/steps/{step_two['id']}",
        params={"workspace_id": workspace_id},
        json={"step_number": 99},
        headers=headers,
    )
    await client.patch(
        f"/api/v1/campaigns/{campaign['id']}/steps/{step_one['id']}",
        params={"workspace_id": workspace_id},
        json={"step_number": 2},
        headers=headers,
    )
    response = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}/steps/{step_two['id']}",
        params={"workspace_id": workspace_id},
        json={"step_number": 1},
        headers=headers,
    )
    assert response.status_code == 200

    campaign_response = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", params={"workspace_id": workspace_id}, headers=headers
    )
    steps = sorted(campaign_response.json()["steps"], key=lambda s: s["step_number"])
    assert steps[0]["id"] == step_two["id"]
    assert steps[1]["id"] == step_one["id"]


async def test_delete_campaign_step_removes_it(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    campaign = await _create_campaign(client, headers, workspace_id)
    step = await _add_step(client, headers, workspace_id, campaign["id"])

    response = await client.delete(
        f"/api/v1/campaigns/{campaign['id']}/steps/{step['id']}",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 204

    campaign_response = await client.get(
        f"/api/v1/campaigns/{campaign['id']}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert campaign_response.json()["steps"] == []


async def test_update_and_delete_step_404_for_unknown_step(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    campaign = await _create_campaign(client, headers, workspace_id)
    fake_step_id = str(uuid.uuid4())

    patch_response = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}/steps/{fake_step_id}",
        params={"workspace_id": workspace_id},
        json={"subject": "x"},
        headers=headers,
    )
    assert patch_response.status_code == 404

    delete_response = await client.delete(
        f"/api/v1/campaigns/{campaign['id']}/steps/{fake_step_id}",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert delete_response.status_code == 404
