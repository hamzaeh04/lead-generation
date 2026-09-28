"""CSV lead export. Suppression filtering is added once the suppression
system exists (Phase 11) — until then this exports all workspace contacts
(or contacts in a single search batch when batch_id is provided).

Columns match the import template so an exported file can be re-imported
with auto-detected column mapping.
"""
from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.contact_repository import ContactRepository
from app.repositories.search_batch_repository import SearchBatchRepository

#: Headers align with csv_import_service synonyms + the downloadable template.
_EXPORT_COLUMNS = (
    "Company Name",
    "Website",
    "Email",
    "First Name",
    "Last Name",
    "Job Title",
    "Phone",
    "City",
    "State",
    "Country",
    "Industry",
    "LinkedIn",
    "Status",
    "Created At",
)


class CsvExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.contacts = ContactRepository(session)
        self.search_batches = SearchBatchRepository(session)

    async def export(
        self, *, workspace_id: uuid.UUID, batch_id: uuid.UUID | None = None
    ) -> str:
        if batch_id is not None:
            batch = await self.search_batches.get_by_id(workspace_id, batch_id)
            if batch is None:
                raise ValueError("Search batch not found")
            contacts = await self.search_batches.list_contacts(batch_id)
        else:
            contacts = await self.contacts.list_for_workspace(workspace_id, limit=100_000, offset=0)

        buffer = io.StringIO()
        # Excel opens UTF-8 CSVs correctly when a BOM is present.
        buffer.write("\ufeff")
        writer = csv.DictWriter(buffer, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        for contact in contacts:
            company = contact.company
            writer.writerow(
                {
                    "Company Name": (company.name if company else "") or "",
                    "Website": (company.website if company else "") or "",
                    "Email": contact.email or "",
                    "First Name": contact.first_name or "",
                    "Last Name": contact.last_name or "",
                    "Job Title": contact.job_title or "",
                    "Phone": contact.phone or "",
                    "City": contact.city or (company.city if company else "") or "",
                    "State": contact.state or (company.state if company else "") or "",
                    "Country": contact.country or (company.country if company else "") or "",
                    "Industry": contact.industry
                    or (company.industry if company else "")
                    or "",
                    "LinkedIn": contact.linkedin_url or "",
                    "Status": contact.status.value if contact.status else "",
                    "Created At": contact.created_at.isoformat() if contact.created_at else "",
                }
            )

        return buffer.getvalue()
