import json
import uuid
from datetime import datetime, timezone

import pytest

from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.provider_config import ProviderConfig
from app.providers.ai.base import AIGenerationRequest, AIGenerationResult
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.models.intent_signal import IntentSignalType

pytestmark = pytest.mark.asyncio


class _StubAIProvider:
    def __init__(self, response: dict):
        self._response = response

    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        return AIGenerationResult(
            text=json.dumps(self._response),
            model="gpt-4o-mini",
            prompt_version=request.prompt_version,
            source_fields_used=list(request.source_fields.keys()),
        )


class _FailingAIProvider:
    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        raise ProviderUnavailableError("openai: simulated outage")


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


async def _make_contact(db_session, workspace_id, *, with_signal=False):
    company = Company(
        workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group", industry="dental", city="Miami"
    )
    db_session.add(company)
    await db_session.flush()

    if with_signal:
        db_session.add(
            IntentSignal(
                workspace_id=uuid.UUID(workspace_id),
                company_id=company.id,
                signal_type=IntentSignalType.EXPANSION,
                provider="manual",
                source="news",
                source_url="https://example.com/news/1",
                signal_text="Acme Dental Group just opened a second location",
                detected_at=datetime.now(timezone.utc),
            )
        )

    contact = Contact(
        workspace_id=uuid.UUID(workspace_id),
        company_id=company.id,
        first_name="Jordan",
        full_name="Jordan Alvarez",
        job_title="Owner",
    )
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


async def test_personalize_persists_and_returns_generation(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id, with_signal=True)

    db_session.add(
        ProviderConfig(provider="openai", category=ProviderCategory.AI, enabled=True, priority=1)
    )
    await db_session.commit()

    response_body = {
        "subject": "Congrats on the new location",
        "opening_line": "Saw the news about your second location.",
        "body": "Wanted to reach out...",
        "cta": "Open to a quick call?",
        "outreach_angle": "Recent expansion",
    }
    monkeypatch.setattr(
        "app.services.personalization_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubAIProvider(response_body),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/personalize",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "Congrats on the new location"
    assert body["personalization_source"] == "intent_signal"
    assert body["source_url"] == "https://example.com/news/1"
    assert "recent_intent_signal" in body["source_fields_used"]
    assert "company_name" in body["source_fields_used"]

    list_response = await client.get(
        f"/api/v1/leads/{contact.id}/personalizations",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert len(list_response.json()) == 1


async def test_personalize_without_intent_signal_has_no_personalization_source(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id, with_signal=False)

    db_session.add(
        ProviderConfig(provider="openai", category=ProviderCategory.AI, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.personalization_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubAIProvider(
            {"subject": "Hi", "body": "...", "cta": "...", "opening_line": "...", "outreach_angle": "..."}
        ),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/personalize",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["personalization_source"] is None
    assert body["source_url"] is None
    assert "recent_intent_signal" not in body["source_fields_used"]


async def test_personalize_rejects_when_no_provider_enabled(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    response = await client.post(
        f"/api/v1/leads/{contact.id}/personalize",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 400


async def test_personalize_reports_missing_credentials(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="openai", category=ProviderCategory.AI, enabled=True, priority=1)
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/leads/{contact.id}/personalize",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 503
    assert "openai" in response.json()["detail"]


async def test_personalize_returns_502_when_provider_fails(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="openai", category=ProviderCategory.AI, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.personalization_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _FailingAIProvider(),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/personalize",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 502


async def test_personalize_404s_for_missing_contact(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        f"/api/v1/leads/{uuid.uuid4()}/personalize",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 404


async def test_personalize_requires_authentication(client):
    response = await client.post(
        f"/api/v1/leads/{uuid.uuid4()}/personalize",
        params={"workspace_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401
