import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import Campaign, CampaignStatus, CampaignStep


class CampaignRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> Campaign:
        campaign = Campaign(**fields)
        self.session.add(campaign)
        return campaign

    async def get_by_id(self, workspace_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign | None:
        result = await self.session.execute(
            select(Campaign)
            .where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
            .options(selectinload(Campaign.steps))
        )
        return result.scalar_one_or_none()

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[Campaign]:
        result = await self.session.execute(
            select(Campaign)
            .where(Campaign.workspace_id == workspace_id)
            .options(selectinload(Campaign.steps))
            .order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all_running(self) -> list[Campaign]:
        """Cross-workspace sweep for the Celery periodic task — not
        workspace-scoped since it's platform-internal, not a user request."""
        result = await self.session.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.RUNNING)
        )
        return list(result.scalars().all())

    def add_step(self, **fields: Any) -> CampaignStep:
        step = CampaignStep(**fields)
        self.session.add(step)
        return step

    async def get_step(self, campaign_id: uuid.UUID, step_number: int) -> CampaignStep | None:
        result = await self.session.execute(
            select(CampaignStep).where(
                CampaignStep.campaign_id == campaign_id, CampaignStep.step_number == step_number
            )
        )
        return result.scalar_one_or_none()

    async def get_step_by_id(self, campaign_id: uuid.UUID, step_id: uuid.UUID) -> CampaignStep | None:
        result = await self.session.execute(
            select(CampaignStep).where(
                CampaignStep.campaign_id == campaign_id, CampaignStep.id == step_id
            )
        )
        return result.scalar_one_or_none()

    async def delete_step(self, step: CampaignStep) -> None:
        await self.session.delete(step)
