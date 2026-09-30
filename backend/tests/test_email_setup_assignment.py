"""One SMTP mailbox can only run one active campaign at a time — the
Start Campaign dialog's email dropdown must show which batch already has
it (and block re-picking it) both in the listing and server-side."""
import uuid

import pytest

from app.models.company import Company
from app.models.contact import Contact

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


async def _make_batch_with_contact(client, db_session, workspace_id, headers, *, email):
    from app.models.search_batch import SearchBatch, SearchBatchContact
    from app.providers.base import ProviderCategory

    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Co")
    db_session.add(company)
    await db_session.flush()
    contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, first_name="Jordan", email=email)
    db_session.add(contact)
    await db_session.flush()
    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id), sequence=1, provider="apollo", category=ProviderCategory.PERSON_DISCOVERY
    )
    db_session.add(batch)
    await db_session.flush()
    db_session.add(SearchBatchContact(batch_id=batch.id, contact_id=contact.id, is_new=True))
    await db_session.commit()
    return batch.id


async def _create_email_setup(client, headers, *, smtp_email):
    response = await client.post(
        "/api/v1/email-setups",
        json={
            "name": "Primary",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_email": smtp_email,
            "smtp_password": "app-password",
            "smtp_use_tls": True,
            "is_default": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_campaign_with_step(client, headers, workspace_id, *, name):
    campaign_response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": name, "from_email": "agency@example.com"},
        headers=headers,
    )
    assert campaign_response.status_code == 201, campaign_response.text
    campaign_id = campaign_response.json()["id"]
    await client.post(
        f"/api/v1/campaigns/{campaign_id}/steps",
        params={"workspace_id": workspace_id},
        json={"step_number": 1, "subject": "Hi", "body": "Hello. {{unsubscribe_url}}"},
        headers=headers,
    )
    return campaign_id


async def test_active_assignment_shown_in_email_setup_listing(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    setup_id = await _create_email_setup(client, headers, smtp_email="sender@agency.example")
    batch_id = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="jordan@acme.example"
    )
    campaign_id = await _create_campaign_with_step(client, headers, workspace_id, name="Q1 Outreach")
    await client.post(f"/api/v1/campaigns/{campaign_id}/start", params={"workspace_id": workspace_id}, headers=headers)

    enroll_response = await client.post(
        f"/api/v1/campaigns/{campaign_id}/enroll",
        params={"workspace_id": workspace_id},
        json={"batch_ids": [str(batch_id)], "email_setup_id": setup_id},
        headers=headers,
    )
    assert enroll_response.status_code == 200, enroll_response.text

    listing = await client.get("/api/v1/email-setups", headers=headers)
    assert listing.status_code == 200
    setup = next(s for s in listing.json() if s["id"] == setup_id)
    assert setup["assigned_batch_id"] == str(batch_id)
    assert setup["assigned_batch_label"] == "Batch 01"


async def test_enrolling_a_different_batch_with_an_assigned_email_is_rejected(
    client, db_session, unique_email
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    setup_id = await _create_email_setup(client, headers, smtp_email="sender2@agency.example")

    batch_1 = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="one@acme.example"
    )
    campaign_1 = await _create_campaign_with_step(client, headers, workspace_id, name="Campaign 1")
    await client.post(f"/api/v1/campaigns/{campaign_1}/start", params={"workspace_id": workspace_id}, headers=headers)
    first_enroll = await client.post(
        f"/api/v1/campaigns/{campaign_1}/enroll",
        params={"workspace_id": workspace_id},
        json={"batch_ids": [str(batch_1)], "email_setup_id": setup_id},
        headers=headers,
    )
    assert first_enroll.status_code == 200

    batch_2 = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="two@acme.example"
    )
    campaign_2 = await _create_campaign_with_step(client, headers, workspace_id, name="Campaign 2")
    await client.post(f"/api/v1/campaigns/{campaign_2}/start", params={"workspace_id": workspace_id}, headers=headers)
    second_enroll = await client.post(
        f"/api/v1/campaigns/{campaign_2}/enroll",
        params={"workspace_id": workspace_id},
        json={"batch_ids": [str(batch_2)], "email_setup_id": setup_id},
        headers=headers,
    )

    assert second_enroll.status_code == 409
    assert "Campaign 1" in second_enroll.json()["detail"] or "Batch 01" in second_enroll.json()["detail"]


async def test_email_freed_up_once_its_campaign_is_cancelled(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    setup_id = await _create_email_setup(client, headers, smtp_email="sender3@agency.example")

    batch_1 = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="one@acme.example"
    )
    campaign_1 = await _create_campaign_with_step(client, headers, workspace_id, name="Campaign 1")
    await client.post(f"/api/v1/campaigns/{campaign_1}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign_1}/enroll",
        params={"workspace_id": workspace_id},
        json={"batch_ids": [str(batch_1)], "email_setup_id": setup_id},
        headers=headers,
    )

    cancel_response = await client.post(
        f"/api/v1/campaigns/{campaign_1}/cancel", params={"workspace_id": workspace_id}, headers=headers
    )
    assert cancel_response.status_code == 200

    batch_2 = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="two@acme.example"
    )
    campaign_2 = await _create_campaign_with_step(client, headers, workspace_id, name="Campaign 2")
    await client.post(f"/api/v1/campaigns/{campaign_2}/start", params={"workspace_id": workspace_id}, headers=headers)
    second_enroll = await client.post(
        f"/api/v1/campaigns/{campaign_2}/enroll",
        params={"workspace_id": workspace_id},
        json={"batch_ids": [str(batch_2)], "email_setup_id": setup_id},
        headers=headers,
    )

    assert second_enroll.status_code == 200, second_enroll.text


async def test_batch_listing_shows_assigned_email_or_none(client, db_session, unique_email):
    """Leads page batch list: each row shows which SMTP account is
    assigned to it (or None), not just the raw email_setup_id."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    setup_id = await _create_email_setup(client, headers, smtp_email="assigned@agency.example")

    assigned_batch = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="one@acme.example"
    )
    campaign_id = await _create_campaign_with_step(client, headers, workspace_id, name="Campaign 1")
    await client.post(f"/api/v1/campaigns/{campaign_id}/start", params={"workspace_id": workspace_id}, headers=headers)
    await client.post(
        f"/api/v1/campaigns/{campaign_id}/enroll",
        params={"workspace_id": workspace_id},
        json={"batch_ids": [str(assigned_batch)], "email_setup_id": setup_id},
        headers=headers,
    )

    unassigned_batch = await _make_batch_with_contact(
        client, db_session, workspace_id, headers, email="two@acme.example"
    )

    listing = await client.get(
        "/api/v1/search-batches", params={"workspace_id": workspace_id}, headers=headers
    )
    assert listing.status_code == 200
    by_id = {b["id"]: b for b in listing.json()}
    assert by_id[str(assigned_batch)]["assigned_email"] == "assigned@agency.example"
    assert by_id[str(unassigned_batch)]["assigned_email"] is None

    detail = await client.get(
        f"/api/v1/search-batches/{assigned_batch}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert detail.json()["assigned_email"] == "assigned@agency.example"
