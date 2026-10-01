"""scoring_active / email_enrichment_active / phone_enrichment_active on
SearchBatchDetail — the "red light" indicator's backing data. Each is true
only when a sweep was actually requested (auto after search, or a manual
"all" click) AND real work is still outstanding, derived fresh from current
contact state so it reads correctly regardless of page navigation and
naturally flips to false once the work finishes, with no explicit
"mark complete" bookkeeping."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.company import Company
from app.models.contact import Contact, ContactSource
from app.models.lead_qualification import LeadQualification
from app.models.search_batch import SearchBatch, SearchBatchContact
from app.providers.base import ProviderCategory

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


async def _make_batch(db_session, workspace_id, *, provider="apollo"):
    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id),
        sequence=1,
        provider=provider,
        category=ProviderCategory.PERSON_DISCOVERY,
    )
    db_session.add(batch)
    await db_session.flush()
    return batch


async def _add_unscored_unrevealed_contact(db_session, workspace_id, batch):
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Co")
    db_session.add(company)
    await db_session.flush()
    contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, first_name="Jordan")
    db_session.add(contact)
    await db_session.flush()
    db_session.add(ContactSource(contact_id=contact.id, provider="apollo", external_id="ext-1"))
    db_session.add(SearchBatchContact(batch_id=batch.id, contact_id=contact.id, is_new=True))
    await db_session.commit()
    return contact


async def _add_scored_revealed_contact(db_session, workspace_id, batch):
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Co 2")
    db_session.add(company)
    await db_session.flush()
    contact = Contact(
        workspace_id=uuid.UUID(workspace_id),
        company_id=company.id,
        first_name="Alex",
        email="alex@acme.example",
        email_reveal_attempted=True,
    )
    db_session.add(contact)
    await db_session.flush()
    db_session.add(
        LeadQualification(
            workspace_id=uuid.UUID(workspace_id),
            contact_id=contact.id,
            provider="stub",
            model="stub-model",
            prompt_version="v1",
            score_version="v1",
            tier="B",
            tier_rationale="Solid fit.",
            composite_score=70,
            confidence=80,
            dimensions={},
            evidence=[],
            overrides_triggered=[],
            missing_data=[],
        )
    )
    db_session.add(SearchBatchContact(batch_id=batch.id, contact_id=contact.id, is_new=True))
    await db_session.commit()
    return contact


async def test_scoring_and_email_enrichment_inactive_when_never_requested(client, db_session, unique_email):
    """An unscored contact alone doesn't mean a sweep is running — a batch
    nobody ever clicked "Score"/"Enrich emails" on (e.g. a fresh manual or
    CSV-imported batch) must not show the indicator as active."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = await _make_batch(db_session, workspace_id)
    await _add_unscored_unrevealed_contact(db_session, workspace_id, batch)

    response = await client.get(
        f"/api/v1/search-batches/{batch.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scoring_active"] is False
    assert body["email_enrichment_active"] is False
    assert body["phone_enrichment_active"] is False


async def test_scoring_and_email_enrichment_active_when_requested_and_outstanding(
    client, db_session, unique_email
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = await _make_batch(db_session, workspace_id)
    await _add_unscored_unrevealed_contact(db_session, workspace_id, batch)
    batch.qualify_requested_at = datetime.now(timezone.utc)
    batch.reveal_requested_at = datetime.now(timezone.utc)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/search-batches/{batch.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scoring_active"] is True
    assert body["email_enrichment_active"] is True


async def test_scoring_and_email_enrichment_inactive_once_completed(client, db_session, unique_email):
    """Requested-at stays set forever (never reset), but once every contact
    has a real result, active must read false — derived from current
    state, not from "was this sweep ever marked done"."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = await _make_batch(db_session, workspace_id)
    await _add_scored_revealed_contact(db_session, workspace_id, batch)
    batch.qualify_requested_at = datetime.now(timezone.utc) - timedelta(hours=1)
    batch.reveal_requested_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/search-batches/{batch.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scoring_active"] is False
    assert body["email_enrichment_active"] is False


async def test_scoring_and_email_enrichment_inactive_once_window_expires_even_if_stuck(
    client, db_session, unique_email
):
    """A reveal that fails for a reason that keeps failing identically
    (e.g. a provider account out of credits) never flips
    email_reveal_attempted, so the contact stays "outstanding" forever —
    without a bounded window this would report active forever even though
    the background sweep that was supposed to handle it already ran."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = await _make_batch(db_session, workspace_id)
    await _add_unscored_unrevealed_contact(db_session, workspace_id, batch)
    batch.qualify_requested_at = datetime.now(timezone.utc) - timedelta(hours=2)
    batch.reveal_requested_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/search-batches/{batch.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scoring_active"] is False
    assert body["email_enrichment_active"] is False


async def test_phone_enrichment_active_within_window_then_expires(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = await _make_batch(db_session, workspace_id)
    contact = await _add_unscored_unrevealed_contact(db_session, workspace_id, batch)
    contact.phone_reveal_attempted = True
    batch.phone_enrich_requested_at = datetime.now(timezone.utc)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/search-batches/{batch.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.json()["phone_enrichment_active"] is True

    # Past the bounded window (same convention the frontend's own polling
    # uses) — Apollo's "no number found" is a permanent, silent miss, so
    # without a cutoff this would read "active" forever.
    batch.phone_enrich_requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/search-batches/{batch.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.json()["phone_enrichment_active"] is False
