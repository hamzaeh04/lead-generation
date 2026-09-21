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
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubPersonDiscoveryProvider(),
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
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _EmptyPersonDiscoveryProvider(),
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
