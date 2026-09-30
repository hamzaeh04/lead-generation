import uuid
from typing import Any, NamedTuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.email_setup import EmailSetup
from app.models.search_batch import SearchBatch


class ActiveAssignment(NamedTuple):
    batch_id: uuid.UUID
    batch_sequence: int
    batch_name: str | None


class EmailSetupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> EmailSetup:
        setup = EmailSetup(**fields)
        self.session.add(setup)
        return setup

    async def get_by_id(self, setup_id: uuid.UUID) -> EmailSetup | None:
        result = await self.session.execute(select(EmailSetup).where(EmailSetup.id == setup_id))
        return result.scalar_one_or_none()

    async def emails_by_ids(self, setup_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        """id -> smtp_email for a batch listing page — one query for every
        row instead of a lookup per batch."""
        if not setup_ids:
            return {}
        result = await self.session.execute(
            select(EmailSetup.id, EmailSetup.smtp_email).where(EmailSetup.id.in_(setup_ids))
        )
        return dict(result.all())

    async def get_by_email(
        self,
        smtp_email: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> EmailSetup | None:
        stmt = select(EmailSetup).where(
            func.lower(EmailSetup.smtp_email) == smtp_email.strip().lower()
        )
        if exclude_id is not None:
            stmt = stmt.where(EmailSetup.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[EmailSetup]:
        result = await self.session.execute(
            select(EmailSetup).order_by(EmailSetup.is_default.desc(), EmailSetup.created_at.desc())
        )
        return list(result.scalars().all())

    async def clear_default(self, *, except_id: uuid.UUID | None = None) -> None:
        stmt = update(EmailSetup).where(EmailSetup.is_default.is_(True)).values(is_default=False)
        if except_id is not None:
            stmt = stmt.where(EmailSetup.id != except_id)
        await self.session.execute(stmt)

    async def delete(self, setup: EmailSetup) -> None:
        await self.session.delete(setup)

    async def active_assignments(self) -> dict[uuid.UUID, ActiveAssignment]:
        """email_setup_id -> which batch currently has it committed, for
        every batch whose campaign hasn't finished yet (status not
        completed/cancelled) — across every workspace, since EmailSetup
        itself is global. One SMTP mailbox sending two campaigns at once
        is never what's wanted, so the same account can't be picked again
        for a new campaign until the one using it now is done."""
        result = await self.session.execute(
            select(SearchBatch.email_setup_id, SearchBatch.id, SearchBatch.sequence, SearchBatch.criteria_snapshot)
            .join(Campaign, Campaign.id == SearchBatch.outreach_campaign_id)
            .where(
                SearchBatch.email_setup_id.is_not(None),
                Campaign.status.not_in([CampaignStatus.COMPLETED, CampaignStatus.CANCELLED]),
            )
        )
        assignments: dict[uuid.UUID, ActiveAssignment] = {}
        for email_setup_id, batch_id, sequence, criteria_snapshot in result.all():
            name = (criteria_snapshot or {}).get("name")
            assignments[email_setup_id] = ActiveAssignment(
                batch_id=batch_id,
                batch_sequence=sequence,
                batch_name=name.strip() if isinstance(name, str) and name.strip() else None,
            )
        return assignments
