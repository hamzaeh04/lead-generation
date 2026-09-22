import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_setup import EmailSetup


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
