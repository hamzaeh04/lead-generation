import json

import pytest

pytestmark = pytest.mark.asyncio

SAMPLE_CSV = (
    "Company Name,Website,Email,First Name,Last Name,Job Title,City,State\n"
    "Acme Dental Group,acmedental.example,jordan@acmedental.example,Jordan,Alvarez,Owner,Miami,FL\n"
    "Sunshine Roofing Co,sunshineroofing.example,sam@sunshineroofing.example,Sam,Chen,CEO,Dallas,TX\n"
    ",,not-an-email-or-name,,,,,\n"
)

DEFAULT_MAPPING = {
    "company": "Company Name",
    "website": "Website",
    "email": "Email",
    "first_name": "First Name",
    "last_name": "Last Name",
    "job_title": "Job Title",
    "city": "City",
    "state": "State",
}


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


async def test_import_preview_detects_headers_and_suggests_mapping(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/leads/import/preview",
        params={"workspace_id": workspace_id},
        files={"file": ("leads.csv", SAMPLE_CSV.encode(), "text/csv")},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 3
    assert body["suggested_mapping"]["company"] == "Company Name"
    assert body["suggested_mapping"]["email"] == "Email"
    assert len(body["sample_rows"]) == 3


async def test_import_creates_companies_and_contacts(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/leads/import",
        params={"workspace_id": workspace_id},
        files={"file": ("leads.csv", SAMPLE_CSV.encode(), "text/csv")},
        data={"mapping_json": json.dumps(DEFAULT_MAPPING)},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 3
    assert body["companies_created"] == 2
    assert body["contacts_created"] == 2
    assert body["skipped_invalid"] == 1
    assert len(body["errors"]) == 1

    leads_response = await client.get(
        "/api/v1/leads", params={"workspace_id": workspace_id}, headers=headers
    )
    leads = leads_response.json()
    assert len(leads) == 2
    emails = {lead["email"] for lead in leads}
    assert emails == {"jordan@acmedental.example", "sam@sunshineroofing.example"}

    companies_response = await client.get(
        "/api/v1/companies", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(companies_response.json()) == 2


async def test_reimporting_same_csv_does_not_duplicate(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    for _ in range(2):
        response = await client.post(
            "/api/v1/leads/import",
            params={"workspace_id": workspace_id},
            files={"file": ("leads.csv", SAMPLE_CSV.encode(), "text/csv")},
            data={"mapping_json": json.dumps(DEFAULT_MAPPING)},
            headers=headers,
        )
        assert response.status_code == 200

    second_result = response.json()
    assert second_result["companies_matched"] == 2
    assert second_result["contacts_matched"] == 2
    assert second_result["companies_created"] == 0
    assert second_result["contacts_created"] == 0

    leads_response = await client.get(
        "/api/v1/leads", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(leads_response.json()) == 2


async def test_export_returns_csv_with_imported_leads(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    await client.post(
        "/api/v1/leads/import",
        params={"workspace_id": workspace_id},
        files={"file": ("leads.csv", SAMPLE_CSV.encode(), "text/csv")},
        data={"mapping_json": json.dumps(DEFAULT_MAPPING)},
        headers=headers,
    )

    response = await client.get(
        "/api/v1/leads/export", params={"workspace_id": workspace_id}, headers=headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert "Acme Dental Group" in body
    assert "jordan@acmedental.example" in body
    assert "First Name" in body
    assert "Jordan" in body


async def test_import_into_batch_links_contacts(client, db_session, unique_email):
    import uuid

    from app.models.search_batch import SearchBatch
    from app.providers.base import ProviderCategory

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    batch = SearchBatch(
        workspace_id=uuid.UUID(workspace_id),
        sequence=1,
        provider="apollo",
        category=ProviderCategory.PERSON_DISCOVERY,
        criteria_snapshot={},
    )
    db_session.add(batch)
    await db_session.commit()
    batch_id = str(batch.id)

    response = await client.post(
        "/api/v1/leads/import",
        params={"workspace_id": workspace_id, "batch_id": batch_id},
        files={"file": ("leads.csv", SAMPLE_CSV.encode(), "text/csv")},
        data={"mapping_json": json.dumps(DEFAULT_MAPPING)},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["contacts_created"] == 2

    batch_response = await client.get(
        f"/api/v1/search-batches/{batch_id}",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert batch_response.status_code == 200
    detail = batch_response.json()
    assert len(detail["contacts"]) == 2
    assert detail["contacts_created"] == 2

    export_response = await client.get(
        "/api/v1/leads/export",
        params={"workspace_id": workspace_id, "batch_id": batch_id},
        headers=headers,
    )
    assert export_response.status_code == 200
    assert "jordan@acmedental.example" in export_response.text
    assert "sam@sunshineroofing.example" in export_response.text


async def test_import_requires_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)
    other_workspace_id = "00000000-0000-0000-0000-000000000000"

    response = await client.post(
        "/api/v1/leads/import/preview",
        params={"workspace_id": other_workspace_id},
        files={"file": ("leads.csv", SAMPLE_CSV.encode(), "text/csv")},
        headers=headers,
    )

    assert response.status_code == 403


async def test_leads_endpoints_require_authentication(client):
    response = await client.get(
        "/api/v1/leads", params={"workspace_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 401
