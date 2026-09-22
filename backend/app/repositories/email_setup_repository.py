import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_setup import EmailSetup


class EmailSetupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> EmailSetup:
        setup = EmailSetup(**fields)
        self.session.add(setup)
        return setup

    async def get_by_id(self, workspace_id: uuid.UUID, setup_id: uuid.UUID) -> EmailSetup | None:
        result = await self.session.execute(
            select(EmailSetup).where(
                EmailSetup.id == setup_id, EmailSetup.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[EmailSetup]:
        result = await self.session.execute(
            select(EmailSetup)
            .where(EmailSetup.workspace_id == workspace_id)
            .order_by(EmailSetup.is_default.desc(), EmailSetup.created_at.desc())
        )
        return list(result.scalars().all())

    async def clear_default(self, workspace_id: uuid.UUID, *, except_id: uuid.UUID | None = None) -> None:
        stmt = (
            update(EmailSetup)
            .where(EmailSetup.workspace_id == workspace_id, EmailSetup.is_default.is_(True))
            .values(is_default=False)
        )
        if except_id is not None:
            stmt = stmt.where(EmailSetup.id != except_id)
        await self.session.execute(stmt)

    async def delete(self, setup: EmailSetup) -> None:
        await self.session.delete(setup)
