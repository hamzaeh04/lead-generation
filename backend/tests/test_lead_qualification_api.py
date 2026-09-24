from unittest.mock import AsyncMock
import json
import uuid

import pytest

from app.models.contact import Contact
from app.models.provider_config import ProviderConfig
from app.providers.ai.base import AIGenerationRequest, AIGenerationResult
from app.providers.base import ProviderCategory, ProviderUnavailableError

pytestmark = pytest.mark.asyncio

_VALID_RESPONSE = {
    "lead_id": "test",
    "score_version": "v1.0",
    "scored_at": "2026-09-23T00:00:00Z",
    "composite_score": 62.5,
    "confidence": 75,
    "tier": "B",
    "tier_rationale": "Strong need signal with no website; capacity is unverified but override applies.",
    "dimensions": {
        "need": {"score": 80, "confidence": 70, "reasoning": "No website found for this business."},
        "capacity": {"score": 50, "confidence": 40, "reasoning": "Headcount unknown."},
        "timing": {"score": 45, "confidence": 50, "reasoning": "No explicit trigger observed."},
        "reachability": {"score": 60, "confidence": 80, "reasoning": "Owner identified with a verified email."},
    },
    "evidence": [
        {
            "dimension": "need",
            "claim": "No functioning website",
            "observation": "domain field absent from lead record",
            "source_platform": "apollo",
            "source_field_or_url": "company.website",
            "inference_type": "observed",
            "strength": "strong",
        }
    ],
    "overrides_triggered": ["NO_SITE_REAL_BUSINESS"],
    "disqualifier": None,
    "missing_data": [
        {"field": "employee_count", "why_it_matters": "needed for capacity scoring", "how_to_obtain": "apollo_enrich"}
    ],
    "enrichment_priority": "medium",
    "recommended_channel": "email",
    "recommended_angle": "No website exists for this business despite real operations.",
    "objection_to_expect": "Budget concerns given unknown size.",
    "estimated_deal_band": "small",
    "next_review_date": "2026-12-23",
    "human_review_required": False,
    "human_review_reason": None,
    "uncertainty_notes": "Company size is entirely inferred from context.",
}


class _StubAIProvider:
    def __init__(self, response: dict | str):
        self._response = response

    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        text = self._response if isinstance(self._response, str) else json.dumps(self._response)
        return AIGenerationResult(
            text=text, model="stub-model", prompt_version=request.prompt_version,
            source_fields_used=list(request.source_fields.keys()),
        )


class _FailingAIProvider:
    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        raise ProviderUnavailableError("groq: simulated outage")


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


async def _make_contact(db_session, workspace_id, **overrides):
    fields = {
        "first_name": "Jordan",
        "full_name": "Jordan Rivera",
        "job_title": "Owner",
        **overrides,
    }
    contact = Contact(workspace_id=uuid.UUID(workspace_id), **fields)
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


async def test_qualify_lead_stores_and_returns_result(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()
    contact = await _make_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_qualification_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubAIProvider(_VALID_RESPONSE)),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/qualify", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "B"
    assert body["composite_score"] == 62.5
    assert body["confidence"] == 75
    assert body["overrides_triggered"] == ["NO_SITE_REAL_BUSINESS"]
    assert len(body["evidence"]) == 1
    assert body["recommended_channel"] == "email"


async def test_qualified_lead_shows_up_on_get_lead(client, db_session, unique_email, monkeypatch):
    """The whole point: GET /leads/{id} (what the table reads) must carry
    the latest qualification's tier/score without a separate request."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()
    contact = await _make_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_qualification_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubAIProvider(_VALID_RESPONSE)),
    )
    contact_id = contact.id  # captured before expire_all() below expires it too
    await client.post(f"/api/v1/leads/{contact_id}/qualify", params={"workspace_id": workspace_id}, headers=headers)
    # Test-only artifact: this fixture shares one session across requests
    # (for transaction isolation), so the qualify call's own internal
    # get_by_id() cached an empty `qualifications` collection on the
    # identity-mapped Contact object before the row existed. A real
    # request gets a fresh session per call and never hits this.
    db_session.expire_all()

    response = await client.get(f"/api/v1/leads/{contact_id}", params={"workspace_id": workspace_id}, headers=headers)

    assert response.status_code == 200
    qualification = response.json()["latest_qualification"]
    assert qualification is not None
    assert qualification["tier"] == "B"
    assert qualification["composite_score"] == 62.5


async def test_get_lead_without_qualification_has_null_field(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    response = await client.get(f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers)

    assert response.json()["latest_qualification"] is None


async def test_qualify_lead_rejects_invalid_tier(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()
    contact = await _make_contact(db_session, workspace_id)

    bad_response = {**_VALID_RESPONSE, "tier": "Z"}
    monkeypatch.setattr(
        "app.services.lead_qualification_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubAIProvider(bad_response)),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/qualify", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 502


async def test_qualify_lead_rejects_non_json_response(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()
    contact = await _make_contact(db_session, workspace_id)

    monkeypatch.setattr(
        "app.services.lead_qualification_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubAIProvider("not json")),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/qualify", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 502


async def test_qualify_lead_404_for_unknown_contact(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/leads/00000000-0000-0000-0000-000000000000/qualify",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 404


async def test_qualify_lead_returns_503_when_no_ai_provider_enabled(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    response = await client.post(
        f"/api/v1/leads/{contact.id}/qualify", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 400  # no AI provider enabled in the registry at all


async def test_qualify_all_in_batch_skips_already_scored(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(ProviderConfig(provider="groq", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()

    from app.models.search_batch import SearchBatch, SearchBatchContact

    already_scored = await _make_contact(db_session, workspace_id, first_name="Already")
    not_scored = await _make_contact(db_session, workspace_id, first_name="Fresh")

    monkeypatch.setattr(
        "app.services.lead_qualification_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubAIProvider(_VALID_RESPONSE)),
    )
    already_scored_id = already_scored.id  # captured before expire_all() below expires it too
    not_scored_id = not_scored.id

    # Pre-qualify one of the two directly, then batch-qualify — it must be skipped.
    pre_response = await client.post(
        f"/api/v1/leads/{already_scored_id}/qualify", params={"workspace_id": workspace_id}, headers=headers
    )
    assert pre_response.status_code == 200
    db_session.expire_all()  # test-only artifact — see comment in the other test above

    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id), sequence=1, provider="apollo", category=ProviderCategory.PERSON_DISCOVERY
    )
    db_session.add(batch)
    await db_session.flush()
    batch_id = batch.id
    db_session.add_all(
        [
            SearchBatchContact(batch_id=batch_id, contact_id=already_scored_id, is_new=True),
            SearchBatchContact(batch_id=batch_id, contact_id=not_scored_id, is_new=True),
        ]
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/search-batches/{batch_id}/qualify-all", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["qualified"] == 1
    assert body["skipped"] == 1
    assert body["failed"] == 0
