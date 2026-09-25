from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select

from app.models.provider_config import ProviderConfig
from app.providers.base import DiscoveryCriteria, NormalizedContact, ProviderCategory, ProviderMetadata
from app.providers.people_sources.base import PersonDiscoveryProvider

pytestmark = pytest.mark.asyncio


class _StubPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "stub"
    category = ProviderCategory.PERSON_DISCOVERY

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        return [
            NormalizedContact(
                metadata=ProviderMetadata(provider="stub", external_id="stub-person-1"),
                first_name="Jane",
                last_name="Doe",
                full_name="Jane Doe",
                job_title="VP of Sales",
                email="jane@example.com",
                company_name="Acme Inc",
                company_domain="acme.example",
            )
        ]

    async def discover_decision_makers(self, company_domain, target_titles):
        return []


class _EmptyPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "stub"
    category = ProviderCategory.PERSON_DISCOVERY

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        return []

    async def discover_decision_makers(self, company_domain, target_titles):
        return []


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
    access_token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    workspaces_response = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces_response.json()[0]["id"]
    return headers, workspace_id


async def _run_search(client, db_session, headers, workspace_id, monkeypatch, *, job_titles=None):
    existing = await db_session.execute(
        select(ProviderConfig).where(
            ProviderConfig.provider == "stub",
            ProviderConfig.category == ProviderCategory.PERSON_DISCOVERY,
        )
    )
    if existing.scalar_one_or_none() is None:
        db_session.add(
            ProviderConfig(
                provider="stub", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1
            )
        )
        await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubPersonDiscoveryProvider()),
    )

    return await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "person_discovery",
            "criteria": {"job_titles": job_titles or ["VP of Sales"]},
        },
        headers=headers,
    )


async def test_search_execute_returns_batch_id(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    response = await _run_search(client, db_session, headers, workspace_id, monkeypatch)

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"]
    assert body["contacts_created"] == 1


async def test_search_batches_list_shows_sequential_batches(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    await _run_search(client, db_session, headers, workspace_id, monkeypatch)
    await _run_search(client, db_session, headers, workspace_id, monkeypatch)

    response = await client.get(
        "/api/v1/search-batches", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    batches = response.json()
    assert len(batches) == 2
    # newest first
    assert batches[0]["sequence"] == 2
    assert batches[1]["sequence"] == 1
    for batch in batches:
        assert batch["provider"] == "stub"
        # first run creates the contact, the re-run just re-matches it —
        # either way each batch touched exactly one lead
        assert batch["contacts_created"] + batch["contacts_matched"] == 1


async def test_search_batch_detail_lists_its_contacts(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    execute_response = await _run_search(client, db_session, headers, workspace_id, monkeypatch)
    batch_id = execute_response.json()["batch_id"]

    response = await client.get(
        f"/api/v1/search-batches/{batch_id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sequence"] == 1
    assert len(body["contacts"]) == 1
    assert body["contacts"][0]["full_name"] == "Jane Doe"
    assert body["criteria_snapshot"]["job_titles"] == ["VP of Sales"]


async def test_search_batch_matched_contact_lands_in_second_batch_too(
    client, db_session, unique_email, monkeypatch
):
    """Re-running the same search matches (not re-creates) the same contact
    — that contact should show up in both batches' listings, since both
    runs genuinely returned it."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    first = await _run_search(client, db_session, headers, workspace_id, monkeypatch)
    second = await _run_search(client, db_session, headers, workspace_id, monkeypatch)

    assert second.json()["contacts_matched"] == 1
    assert second.json()["contacts_created"] == 0

    for execute_response in (first, second):
        batch_id = execute_response.json()["batch_id"]
        detail = await client.get(
            f"/api/v1/search-batches/{batch_id}",
            params={"workspace_id": workspace_id},
            headers=headers,
        )
        assert len(detail.json()["contacts"]) == 1


async def test_search_batch_detail_404_for_unknown_batch(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.get(
        "/api/v1/search-batches/00000000-0000-0000-0000-000000000000",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 404


async def test_search_batches_require_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)

    response = await client.get(
        "/api/v1/search-batches",
        params={"workspace_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 403


async def test_zero_result_search_creates_no_batch(client, db_session, unique_email, monkeypatch):
    """Regression test: a search that finds nothing must not leave behind
    an empty "Batch NN — 0 leads" row cluttering the Leads page."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="stub", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_EmptyPersonDiscoveryProvider()),
    )

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "person_discovery",
            "criteria": {"job_titles": ["Nobody Matches This"]},
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["batch_id"] is None

    batches = await client.get(
        "/api/v1/search-batches", params={"workspace_id": workspace_id}, headers=headers
    )
    assert batches.json() == []


async def test_search_execute_auto_qualifies_new_leads(client, db_session, unique_email, monkeypatch):
    """Regression test: leads must be scored automatically after a search,
    without a separate manual step — but qualification now runs as a
    background task (see qualify_contacts_in_background in
    search_service.py) rather than blocking the search response, since
    awaiting it inline could hold a large batch's HTTP request open for
    minutes. So the immediate response's latest_qualification is still
    None; this asserts the score lands once the background task (which
    the in-process ASGI test client awaits as part of the same call)
    completes, via a follow-up GET."""
    import json

    from app.providers.ai.base import AIGenerationRequest, AIGenerationResult

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="stub", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1
        )
    )
    db_session.add(ProviderConfig(provider="anthropic", category=ProviderCategory.AI, enabled=True, priority=1))
    await db_session.commit()

    ai_response = {
        "composite_score": 70,
        "confidence": 80,
        "tier": "B",
        "tier_rationale": "Strong reachability signal.",
        "dimensions": {},
        "evidence": [],
        "overrides_triggered": [],
        "disqualifier": None,
        "missing_data": [],
    }

    class _StubAIProvider:
        async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
            return AIGenerationResult(
                text=json.dumps(ai_response), model="stub-model", prompt_version=request.prompt_version,
                source_fields_used=list(request.source_fields.keys()),
            )

    async def _build_provider(session, workspace_id, provider_name, category, settings):
        return _StubAIProvider() if provider_name == "anthropic" else _StubPersonDiscoveryProvider()

    class _SharedSessionContextManager:
        """qualify_contacts_in_background opens its own AsyncSessionLocal()
        session in production (the request-scoped test `db_session` is
        closed by the time a background task runs) — but the test fixtures
        share one in-memory SQLite `db_session` for the whole test, so the
        background task must reuse that same session/engine instead of a
        real AsyncSessionLocal() pointed at a Postgres URL that doesn't
        exist in this sandbox."""

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc_info):
            return False

    # search_service and lead_qualification_service both `from app.services
    # import provider_factory` — same module object either way, so one
    # patch (dispatching on provider_name) covers both call sites.
    monkeypatch.setattr("app.services.provider_factory.build_provider_for_workspace", _build_provider)
    monkeypatch.setattr("app.services.lead_qualification_service._BATCH_PACING_SECONDS", 0)
    monkeypatch.setattr(
        "app.services.search_service.AsyncSessionLocal", lambda: _SharedSessionContextManager()
    )

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "person_discovery",
            "criteria": {"job_titles": ["VP of Sales"]},
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["contacts"]) == 1
    assert body["contacts"][0]["latest_qualification"] is None
    contact_id = body["contacts"][0]["id"]

    db_session.expire_all()
    lead_response = await client.get(
        f"/api/v1/leads/{contact_id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.status_code == 200
    qualification = lead_response.json()["latest_qualification"]
    assert qualification is not None
    assert qualification["tier"] == "B"
    assert qualification["composite_score"] == 70


async def test_search_execute_auto_reveals_apollo_leads_but_not_phone(
    client, db_session, unique_email, monkeypatch
):
    """Regression test: Apollo leads must come back unmasked automatically
    (no manual Reveal button anymore), but phone must never be stored per
    explicit instruction even though the provider returns one."""

    class _StubApolloDiscoveryProvider(_StubPersonDiscoveryProvider):
        name = "apollo"

        async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
            return [
                NormalizedContact(
                    metadata=ProviderMetadata(provider="apollo", external_id="apollo-1"),
                    first_name="Jane",
                    full_name="Jane",
                    job_title="VP of Sales",
                    company_name="Acme Inc",
                    company_domain="acme.example",
                )
            ]

        async def reveal(self, external_id: str, *, raw_reference=None) -> dict | None:
            return {
                "first_name": "Jane",
                "last_name": "Doe",
                "full_name": "Jane Doe",
                "email": "jane@acme.example",
                "phone": "+15550100099",
                "email_status": "verified",
                "linkedin_url": "https://linkedin.com/in/janedoe",
                "city": None,
                "state": None,
                "country": None,
                "seniority": None,
                "department": None,
                "organization": None,
            }

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="apollo", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubApolloDiscoveryProvider()),
    )

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apollo",
            "category": "person_discovery",
            "criteria": {"job_titles": ["VP of Sales"]},
        },
        headers=headers,
    )

    assert response.status_code == 200
    contact = response.json()["contacts"][0]
    assert contact["email"] == "jane@acme.example"
    assert contact["linkedin_url"] == "https://linkedin.com/in/janedoe"
    assert contact["email_status"] == "verified"
    assert contact["phone"] is None


async def test_reveal_all_in_batch_skips_already_revealed(client, db_session, unique_email, monkeypatch):
    """Manual recovery action (see /reveal-all's docstring): reveals every
    not-yet-revealed contact in a batch, skipping anything that already has
    an email — so re-running this after a partial failure never re-spends
    a credit on a lead that's already done."""
    import uuid

    from app.models.contact import Contact
    from app.models.search_batch import SearchBatch, SearchBatchContact
    from app.repositories.contact_repository import ContactRepository

    class _StubApolloRevealProvider(PersonDiscoveryProvider):
        name = "apollo"
        category = ProviderCategory.PERSON_DISCOVERY

        async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
            return []

        async def discover_decision_makers(self, company_domain: str, target_titles: list[str]):
            return []

        async def reveal(self, external_id: str, *, raw_reference=None) -> dict | None:
            return {"email": "fresh@acme.example", "first_name": "Fresh"}

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="apollo", category=ProviderCategory.PERSON_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.lead_reveal_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubApolloRevealProvider()),
    )

    already_revealed = Contact(
        workspace_id=uuid.UUID(workspace_id), first_name="Already", full_name="Already", email="already@acme.example"
    )
    not_revealed = Contact(workspace_id=uuid.UUID(workspace_id), first_name="Fresh", full_name="Fresh")
    db_session.add_all([already_revealed, not_revealed])
    await db_session.flush()

    contact_repo = ContactRepository(db_session)
    contact_repo.add_source(
        contact=already_revealed, provider="apollo", external_id="apollo-1", source_url=None,
        source_type="api", raw_reference={"id": "apollo-1"},
    )
    contact_repo.add_source(
        contact=not_revealed, provider="apollo", external_id="apollo-2", source_url=None,
        source_type="api", raw_reference={"id": "apollo-2"},
    )
    await db_session.commit()
    already_revealed_id = already_revealed.id
    not_revealed_id = not_revealed.id

    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id), sequence=1, provider="apollo", category=ProviderCategory.PERSON_DISCOVERY
    )
    db_session.add(batch)
    await db_session.flush()
    batch_id = batch.id
    db_session.add_all(
        [
            SearchBatchContact(batch_id=batch_id, contact_id=already_revealed_id, is_new=True),
            SearchBatchContact(batch_id=batch_id, contact_id=not_revealed_id, is_new=True),
        ]
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/search-batches/{batch_id}/reveal-all", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["revealed"] == 1
    assert body["skipped"] == 1

    db_session.expire_all()
    lead_response = await client.get(
        f"/api/v1/leads/{not_revealed_id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.json()["email"] == "fresh@acme.example"


async def test_enrich_phones_rejects_non_apollo_batch(client, db_session, unique_email):
    import uuid

    from app.models.search_batch import SearchBatch

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id), sequence=1, provider="smartlead", category=ProviderCategory.PERSON_DISCOVERY
    )
    db_session.add(batch)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/search-batches/{batch.id}/enrich-phones", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 400
    assert "Apollo" in response.json()["detail"]


async def test_enrich_phones_returns_503_when_public_base_url_unset(
    client, db_session, unique_email, monkeypatch
):
    import uuid

    from app.core.config import get_settings
    from app.models.search_batch import SearchBatch

    # A developer's real backend/.env (with a live PUBLIC_BASE_URL) is
    # loaded into the process-wide cached Settings instance, so this can't
    # rely on it being ambiently unset — force it off for this test.
    monkeypatch.setattr(get_settings(), "PUBLIC_BASE_URL", None)

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id), sequence=1, provider="apollo", category=ProviderCategory.PERSON_DISCOVERY
    )
    db_session.add(batch)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/search-batches/{batch.id}/enrich-phones", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 503


async def test_enrich_phones_requests_and_skips_already_attempted(
    client, db_session, unique_email, monkeypatch
):
    """Regression test: requesting phone reveal only kicks off Apollo's
    async lookup (see PhoneEnrichmentService) — the number itself lands
    later via the /apollo/phone-reveal webhook, simulated here directly
    rather than through a real HTTP callback."""
    import uuid

    from app.core.config import get_settings
    from app.models.contact import Contact
    from app.models.search_batch import SearchBatch, SearchBatchContact
    from app.repositories.contact_repository import ContactRepository

    monkeypatch.setattr(get_settings(), "PUBLIC_BASE_URL", "https://example-tunnel.ngrok-free.dev")
    monkeypatch.setattr(get_settings(), "APOLLO_WEBHOOK_SECRET", None)

    requested_ids: list[str] = []

    class _StubApolloPhoneProvider(_StubPersonDiscoveryProvider):
        name = "apollo"

        async def request_phone_reveal(self, external_id: str, *, webhook_url: str) -> None:
            assert webhook_url == "https://example-tunnel.ngrok-free.dev/api/v1/webhooks/apollo/phone-reveal"
            requested_ids.append(external_id)

    monkeypatch.setattr(
        "app.services.phone_enrichment_service.provider_factory.build_provider_for_workspace",
        AsyncMock(return_value=_StubApolloPhoneProvider()),
    )

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    no_phone_yet = Contact(workspace_id=uuid.UUID(workspace_id), first_name="Fresh", full_name="Fresh")
    already_has_phone = Contact(
        workspace_id=uuid.UUID(workspace_id), first_name="HasPhone", full_name="HasPhone", phone="+15550100001"
    )
    already_attempted = Contact(
        workspace_id=uuid.UUID(workspace_id),
        first_name="Attempted",
        full_name="Attempted",
        phone_reveal_attempted=True,
    )
    db_session.add_all([no_phone_yet, already_has_phone, already_attempted])
    await db_session.flush()

    contact_repo = ContactRepository(db_session)
    for contact, ext_id in [
        (no_phone_yet, "apollo-fresh"),
        (already_has_phone, "apollo-has-phone"),
        (already_attempted, "apollo-attempted"),
    ]:
        contact_repo.add_source(
            contact=contact, provider="apollo", external_id=ext_id, source_url=None,
            source_type="api", raw_reference={"id": ext_id},
        )
    await db_session.commit()
    no_phone_yet_id = no_phone_yet.id  # captured before expire_all() below expires it too

    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id), sequence=1, provider="apollo", category=ProviderCategory.PERSON_DISCOVERY
    )
    db_session.add(batch)
    await db_session.flush()
    db_session.add_all(
        [
            SearchBatchContact(batch_id=batch.id, contact_id=no_phone_yet_id, is_new=True),
            SearchBatchContact(batch_id=batch.id, contact_id=already_has_phone.id, is_new=True),
            SearchBatchContact(batch_id=batch.id, contact_id=already_attempted.id, is_new=True),
        ]
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/search-batches/{batch.id}/enrich-phones", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["requested"] == 1
    assert body["skipped"] == 2
    assert requested_ids == ["apollo-fresh"]

    db_session.expire_all()
    lead_response = await client.get(
        f"/api/v1/leads/{no_phone_yet_id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert lead_response.status_code == 200
    # phone_reveal_attempted isn't exposed on ContactRead, but the DB row
    # should have flipped — verified via a direct query instead.
    refreshed = await db_session.get(Contact, no_phone_yet_id)
    assert refreshed.phone_reveal_attempted is True


async def test_apollo_phone_reveal_webhook_updates_contact(client, db_session, unique_email, monkeypatch):
    """Simulates Apollo's async callback (see docs.apollo.io/docs/
    retrieve-mobile-phone-numbers-for-contacts) landing after a phone
    was requested — confirms the webhook handler matches it back to the
    right contact via ContactSource and fills in the phone."""
    import uuid

    from app.core.config import get_settings

    # A developer's real backend/.env (with a live APOLLO_WEBHOOK_SECRET)
    # is loaded into the process-wide cached Settings instance, so this
    # can't rely on it being ambiently unset — force it off for this test.
    monkeypatch.setattr(get_settings(), "APOLLO_WEBHOOK_SECRET", None)

    from app.models.contact import Contact
    from app.repositories.contact_repository import ContactRepository

    _, workspace_id = await _register_and_get_workspace(client, unique_email)

    contact = Contact(
        workspace_id=uuid.UUID(workspace_id), first_name="Fresh", full_name="Fresh", phone_reveal_attempted=True
    )
    db_session.add(contact)
    await db_session.flush()
    ContactRepository(db_session).add_source(
        contact=contact, provider="apollo", external_id="apollo-webhook-1", source_url=None,
        source_type="api", raw_reference={"id": "apollo-webhook-1"},
    )
    await db_session.commit()
    contact_id = contact.id

    response = await client.post(
        "/api/v1/webhooks/apollo/phone-reveal",
        json={
            "people": [
                {
                    "id": "apollo-webhook-1",
                    "phone_numbers": [{"raw_number": "15550100099", "sanitized_number": "+15550100099"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 1
    assert body["updated"] == 1

    db_session.expire_all()
    refreshed = await db_session.get(Contact, contact_id)
    assert refreshed.phone == "+15550100099"


async def test_apollo_phone_reveal_webhook_rejects_wrong_secret(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "APOLLO_WEBHOOK_SECRET", "correct-secret")

    response = await client.post(
        "/api/v1/webhooks/apollo/phone-reveal",
        params={"secret": "wrong-secret"},
        json={"people": []},
    )

    assert response.status_code == 401
