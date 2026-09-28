"""CSV lead import: parse -> preview/mapping -> normalize -> dedup -> persist.

Every imported row becomes a CompanySource/ContactSource tagged
provider="csv_import" so imported records carry the same provenance
guarantees as provider-discovered ones — a CSV row is a legitimate source,
never treated as more or less trustworthy than an API response by default.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import NormalizedCompany, NormalizedContact, ProviderMetadata
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.search_batch_repository import SearchBatchRepository
from app.schemas.csv_import import (
    IMPORTABLE_FIELDS,
    ImportMapping,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportResultResponse,
    ImportRowError,
)
from app.services.company_resolver import CompanyEntityResolver
from app.services.contact_resolver import PersonEntityResolver

_HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "company": ("company", "company name", "organization", "org", "business name"),
    "website": ("website", "url", "domain", "site"),
    "email": ("email", "email address", "e-mail"),
    "first_name": ("first name", "firstname", "first"),
    "last_name": ("last name", "lastname", "last", "surname"),
    "job_title": ("job title", "title", "position", "role"),
    "phone": ("phone", "phone number", "telephone", "mobile"),
    "city": ("city",),
    "state": ("state", "province", "region"),
    "country": ("country",),
    "industry": ("industry", "sector", "vertical"),
}


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode CSV file (unsupported encoding)")


def _valid_email_or_none(value: str) -> str | None:
    """Syntax-only check (no deliverability lookup) — a CSV cell that isn't
    even a well-formed email must never be stored/treated as one."""
    if not value:
        return None
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def _parse_rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = _decode(content)
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = [dict(row) for row in reader]
    return headers, rows


def suggest_mapping(headers: list[str]) -> dict[str, str]:
    lowered = {h: h.strip().lower() for h in headers}
    mapping: dict[str, str] = {}
    for canonical_field, synonyms in _HEADER_SYNONYMS.items():
        for header, lowered_header in lowered.items():
            if lowered_header in synonyms:
                mapping[canonical_field] = header
                break
    return mapping


def preview_csv(content: bytes, *, sample_size: int = 10) -> ImportPreviewResponse:
    headers, rows = _parse_rows(content)
    sample = [
        ImportPreviewRow(row_number=i + 1, values=row) for i, row in enumerate(rows[:sample_size])
    ]
    return ImportPreviewResponse(
        headers=headers,
        suggested_mapping=suggest_mapping(headers),
        sample_rows=sample,
        total_rows=len(rows),
    )


class CsvImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.company_resolver = CompanyEntityResolver(CompanyRepository(session))
        self.contact_resolver = PersonEntityResolver(ContactRepository(session))
        self.search_batches = SearchBatchRepository(session)

    async def execute(
        self,
        *,
        workspace_id: uuid.UUID,
        content: bytes,
        mapping: ImportMapping,
        batch_id: uuid.UUID | None = None,
    ) -> ImportResultResponse:
        unknown_fields = set(mapping.mapping) - set(IMPORTABLE_FIELDS)
        if unknown_fields:
            raise ValueError(f"Unknown mapping field(s): {', '.join(sorted(unknown_fields))}")

        batch = None
        linked_contact_ids: set[uuid.UUID] = set()
        if batch_id is not None:
            batch = await self.search_batches.get_by_id(workspace_id, batch_id)
            if batch is None:
                raise ValueError("Search batch not found")
            linked_contact_ids = set(await self.search_batches.list_contact_ids(batch_id))

        _, rows = _parse_rows(content)

        companies_created = companies_matched = 0
        contacts_created = contacts_matched = 0
        skipped_invalid = 0
        errors: list[ImportRowError] = []
        batch_companies_created = batch_companies_matched = 0
        batch_contacts_created = batch_contacts_matched = 0

        for row_number, row in enumerate(rows, start=1):
            values = {
                field: (row.get(header) or "").strip()
                for field, header in mapping.mapping.items()
            }
            if values.get("email"):
                values["email"] = _valid_email_or_none(values["email"]) or ""

            has_company_signal = bool(values.get("company") or values.get("website"))
            has_contact_signal = bool(
                values.get("email") or values.get("first_name") or values.get("last_name")
            )
            if not has_company_signal and not has_contact_signal:
                skipped_invalid += 1
                errors.append(
                    ImportRowError(row_number=row_number, reason="No usable company or contact data")
                )
                continue

            retrieved_at = datetime.now(timezone.utc)
            company_id: uuid.UUID | None = None

            if has_company_signal:
                company_candidate = NormalizedCompany(
                    metadata=ProviderMetadata(
                        provider="csv_import",
                        source_type="csv_import",
                        raw_reference={"row_number": row_number, **row},
                        retrieved_at=retrieved_at,
                    ),
                    name=values.get("company") or None,
                    website=values.get("website") or None,
                    domain=values.get("website") or None,
                    city=values.get("city") or None,
                    state=values.get("state") or None,
                    country=values.get("country") or None,
                    industry=values.get("industry") or None,
                )
                company_resolution = await self.company_resolver.resolve(
                    workspace_id=workspace_id, candidate=company_candidate
                )
                company_id = company_resolution.company.id
                if company_resolution.created:
                    companies_created += 1
                    batch_companies_created += 1
                else:
                    companies_matched += 1
                    batch_companies_matched += 1

            if has_contact_signal:
                contact_candidate = NormalizedContact(
                    metadata=ProviderMetadata(
                        provider="csv_import",
                        source_type="csv_import",
                        raw_reference={"row_number": row_number, **row},
                        retrieved_at=retrieved_at,
                    ),
                    first_name=values.get("first_name") or None,
                    last_name=values.get("last_name") or None,
                    job_title=values.get("job_title") or None,
                    email=values.get("email") or None,
                    phone=values.get("phone") or None,
                )
                contact_resolution = await self.contact_resolver.resolve(
                    workspace_id=workspace_id, candidate=contact_candidate, company_id=company_id
                )
                if contact_resolution.created:
                    contacts_created += 1
                else:
                    contacts_matched += 1

                if batch is not None and contact_resolution.contact.id not in linked_contact_ids:
                    self.search_batches.add_contact(
                        batch=batch,
                        contact_id=contact_resolution.contact.id,
                        is_new=contact_resolution.created,
                    )
                    linked_contact_ids.add(contact_resolution.contact.id)
                    if contact_resolution.created:
                        batch_contacts_created += 1
                    else:
                        batch_contacts_matched += 1

        if batch is not None:
            batch.companies_created += batch_companies_created
            batch.companies_matched += batch_companies_matched
            batch.contacts_created += batch_contacts_created
            batch.contacts_matched += batch_contacts_matched

        await self.session.commit()

        return ImportResultResponse(
            total_rows=len(rows),
            companies_created=companies_created,
            companies_matched=companies_matched,
            contacts_created=contacts_created,
            contacts_matched=contacts_matched,
            skipped_invalid=skipped_invalid,
            errors=errors,
        )
