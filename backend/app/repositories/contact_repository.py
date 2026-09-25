import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company
from app.models.contact import Contact, ContactSource, LeadStatus
from app.models.tag import LeadTag

_SORT_COLUMNS = {
    "created_at": Contact.created_at,
    "last_seen": Contact.last_seen,
    "full_name": Contact.full_name,
}


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> Contact | None:
        result = await self.session.execute(
            select(Contact)
            .where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
            .options(
                selectinload(Contact.company),
                selectinload(Contact.sources),
                selectinload(Contact.qualifications),
                selectinload(Contact.campaign_recipients),
            )
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, workspace_id: uuid.UUID, email: str) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(Contact.workspace_id == workspace_id, Contact.email == email)
        )
        return result.scalars().first()

    async def find_by_linkedin_url(
        self, workspace_id: uuid.UUID, linkedin_url: str
    ) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.workspace_id == workspace_id, Contact.linkedin_url == linkedin_url
            )
        )
        return result.scalars().first()

    async def find_by_name_and_company(
        self, workspace_id: uuid.UUID, full_name: str, company_id: uuid.UUID
    ) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                Contact.company_id == company_id,
                Contact.full_name == full_name,
            )
        )
        return result.scalars().first()

    async def list_for_workspace(
        self, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Contact]:
        result = await self.session.execute(
            select(Contact)
            .where(Contact.workspace_id == workspace_id)
            .options(
                selectinload(Contact.company),
                selectinload(Contact.sources),
                selectinload(Contact.qualifications),
                selectinload(Contact.campaign_recipients),
            )
            .order_by(Contact.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def search(
        self,
        workspace_id: uuid.UUID,
        *,
        status: LeadStatus | None = None,
        tag_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        text: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        stmt = (
            select(Contact)
            .where(Contact.workspace_id == workspace_id)
            .options(
                selectinload(Contact.company),
                selectinload(Contact.sources),
                selectinload(Contact.qualifications),
                selectinload(Contact.campaign_recipients),
            )
        )
        if status is not None:
            stmt = stmt.where(Contact.status == status)
        if company_id is not None:
            stmt = stmt.where(Contact.company_id == company_id)
        if tag_id is not None:
            stmt = stmt.join(LeadTag, LeadTag.contact_id == Contact.id).where(LeadTag.tag_id == tag_id)
        if text:
            pattern = f"%{text.strip().lower()}%"
            stmt = stmt.outerjoin(Company, Company.id == Contact.company_id).where(
                or_(
                    Contact.full_name.ilike(pattern),
                    Contact.email.ilike(pattern),
                    Company.name.ilike(pattern),
                )
            )

        column = _SORT_COLUMNS.get(sort_by, Contact.created_at)
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_for_company(self, workspace_id: uuid.UUID, company_id: uuid.UUID) -> list[Contact]:
        result = await self.session.execute(
            select(Contact).where(
                Contact.workspace_id == workspace_id, Contact.company_id == company_id
            )
        )
        return list(result.scalars().all())

    async def create(self, *, workspace_id: uuid.UUID, **fields: Any) -> Contact:
        contact = Contact(workspace_id=workspace_id, **fields)
        self.session.add(contact)
        await self.session.flush()  # assigns contact.id before it's referenced by a source row
        return contact

    def add_source(
        self,
        *,
        contact: Contact,
        provider: str,
        external_id: str | None,
        source_url: str | None,
        source_type: str,
        raw_reference: dict[str, Any],
    ) -> ContactSource:
        source = ContactSource(
            contact_id=contact.id,
            provider=provider,
            external_id=external_id,
            source_url=source_url,
            source_type=source_type,
            raw_reference=raw_reference,
        )
        self.session.add(source)
        return source

    async def get_source(self, contact_id: uuid.UUID, provider: str) -> ContactSource | None:
        result = await self.session.execute(
            select(ContactSource)
            .where(ContactSource.contact_id == contact_id, ContactSource.provider == provider)
            .order_by(ContactSource.retrieved_at.desc())
        )
        return result.scalars().first()

    async def find_by_provider_external_id(self, provider: str, external_id: str) -> Contact | None:
        """Webhook callbacks (e.g. Apollo's async phone reveal) only carry
        the provider's own person id, not our contact_id/workspace_id — not
        workspace-scoped since a provider's external_id is globally unique
        to that provider, not per-workspace."""
        result = await self.session.execute(
            select(Contact)
            .join(ContactSource, ContactSource.contact_id == Contact.id)
            .where(ContactSource.provider == provider, ContactSource.external_id == external_id)
        )
        return result.scalars().first()
