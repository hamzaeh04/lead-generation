import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_qualification import LeadQualification


class LeadQualificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, *, workspace_id: uuid.UUID, contact_id: uuid.UUID, **fields: Any) -> LeadQualification:
        qualification = LeadQualification(workspace_id=workspace_id, contact_id=contact_id, **fields)
        self.session.add(qualification)
        return qualification

    async def get_latest_for_contact(
        self, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> LeadQualification | None:
        result = await self.session.execute(
            select(LeadQualification)
            .where(
                LeadQualification.workspace_id == workspace_id,
                LeadQualification.contact_id == contact_id,
            )
            .order_by(LeadQualification.scored_at.desc())
            .limit(1)
        )
        return result.scalars().first()
