import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contact import Contact
from app.models.search_batch import SearchBatch, SearchBatchContact
from app.providers.base import ProviderCategory


class SearchBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_sequence(self, workspace_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(SearchBatch.sequence), 0)).where(
                SearchBatch.workspace_id == workspace_id
            )
        )
        return (result.scalar_one() or 0) + 1

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        provider: str,
        category: ProviderCategory,
        criteria_snapshot: dict[str, Any],
        created_by: uuid.UUID | None,
    ) -> SearchBatch:
        sequence = await self.next_sequence(workspace_id)
        batch = SearchBatch(
            workspace_id=workspace_id,
            sequence=sequence,
            provider=provider,
            category=category,
            criteria_snapshot=criteria_snapshot,
            created_by=created_by,
        )
        self.session.add(batch)
        await self.session.flush()  # assigns batch.id before link rows reference it
        return batch

    def add_contact(self, *, batch: SearchBatch, contact_id: uuid.UUID, is_new: bool) -> None:
        self.session.add(
            SearchBatchContact(batch_id=batch.id, contact_id=contact_id, is_new=is_new)
        )

    async def list_for_workspace(
        self, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[SearchBatch]:
        result = await self.session.execute(
            select(SearchBatch)
            .where(SearchBatch.workspace_id == workspace_id)
            .order_by(SearchBatch.sequence.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(self, workspace_id: uuid.UUID, batch_id: uuid.UUID) -> SearchBatch | None:
        result = await self.session.execute(
            select(SearchBatch).where(
                SearchBatch.id == batch_id, SearchBatch.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def list_contact_ids(self, batch_id: uuid.UUID) -> list[uuid.UUID]:
        """IDs only — used by campaign enroll so we don't pull company/sources/qualifications."""
        result = await self.session.execute(
            select(SearchBatchContact.contact_id).where(SearchBatchContact.batch_id == batch_id)
        )
        return list(result.scalars().all())

    async def list_contacts(self, batch_id: uuid.UUID) -> list[Contact]:
        result = await self.session.execute(
            select(Contact)
            .join(SearchBatchContact, SearchBatchContact.contact_id == Contact.id)
            .where(SearchBatchContact.batch_id == batch_id)
            .options(
                selectinload(Contact.company),
                selectinload(Contact.sources),
                selectinload(Contact.qualifications),
                selectinload(Contact.campaign_recipients),
            )
            .order_by(Contact.created_at.desc())
        )
        return list(result.scalars().unique().all())
