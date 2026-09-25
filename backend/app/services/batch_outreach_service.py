"""Auto-generate AI drafts for a search batch, then enroll + send.

Triggered after Discover creates a batch and emails are revealed:
1. Assign a default Email Setup (SMTP) to the batch
2. Generate a personalization draft for every contact that has an email
3. Create a one-step campaign using those drafts as the message
4. Enroll the batch and send immediately

Skips cleanly when there is no SMTP setup or no contacts with email.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import AsyncSessionLocal
from app.models.campaign import CampaignStatus
from app.models.contact import Contact
from app.models.search_batch import SearchBatch
from app.repositories.ai_generation_repository import AIGenerationRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.email_setup_repository import EmailSetupRepository
from app.repositories.search_batch_repository import SearchBatchRepository
from app.services.campaign_service import CampaignService
from app.services.personalization_service import PersonalizationService
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_STEP_SUBJECT = "{{personalized_subject}}"
_DEFAULT_STEP_BODY = "{{personalized_body}}"


class BatchOutreachService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.batches = SearchBatchRepository(session)
        self.email_setups = EmailSetupRepository(session)
        self.campaigns = CampaignRepository(session)
        self.generations = AIGenerationRepository(session)

    async def run(self, *, workspace_id: uuid.UUID, batch_id: uuid.UUID) -> dict:
        batch = await self.batches.get_by_id(workspace_id, batch_id)
        if batch is None:
            return {"status": "skipped", "reason": "batch_not_found"}

        contacts = await self.batches.list_contacts(batch_id)
        with_email = [c for c in contacts if (c.email or "").strip()]
        if not with_email:
            batch.outreach_status = "skipped"
            await self.session.commit()
            return {"status": "skipped", "reason": "no_emails", "drafted": 0, "sent": 0}

        setup = await self._resolve_email_setup(batch)
        if setup is None:
            batch.outreach_status = "skipped"
            await self.session.commit()
            logger.warning(
                "batch_outreach_skipped_no_smtp",
                workspace_id=str(workspace_id),
                batch_id=str(batch_id),
            )
            return {"status": "skipped", "reason": "no_email_setup", "drafted": 0, "sent": 0}

        batch.email_setup_id = setup.id
        batch.outreach_status = "drafting"
        await self.session.commit()

        personalizer = PersonalizationService(self.session, self.settings)
        drafted = 0
        draft_failed = 0
        for contact in with_email:
            existing = await self.generations.list_for_contact(workspace_id, contact.id)
            if existing:
                drafted += 1
                continue
            try:
                await personalizer.personalize(workspace_id=workspace_id, contact_id=contact.id)
                drafted += 1
            except Exception as exc:  # noqa: BLE001 — one bad lead must not stop the batch
                draft_failed += 1
                logger.warning(
                    "batch_outreach_draft_failed",
                    contact_id=str(contact.id),
                    error=str(exc),
                )

        # Only enroll contacts that now have a draft (or already had one).
        ready_ids: list[uuid.UUID] = []
        for contact in with_email:
            gens = await self.generations.list_for_contact(workspace_id, contact.id)
            if gens:
                ready_ids.append(contact.id)

        if not ready_ids:
            batch.outreach_status = "failed"
            await self.session.commit()
            return {
                "status": "failed",
                "reason": "no_drafts",
                "drafted": drafted,
                "draft_failed": draft_failed,
                "sent": 0,
            }

        batch.outreach_status = "sending"
        await self.session.commit()

        campaign = await self._ensure_campaign(workspace_id=workspace_id, batch=batch, setup_email=setup.smtp_email, setup_name=setup.name)
        batch.outreach_campaign_id = campaign.id
        await self.session.commit()

        enroll = await CampaignService(self.session, self.settings).enroll_contacts(
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            contact_ids=ready_ids,
            email_setup_id=setup.id,
            subject=_DEFAULT_STEP_SUBJECT,
            body=_DEFAULT_STEP_BODY,
        )

        batch.outreach_status = "completed"
        await self.session.commit()

        logger.info(
            "batch_outreach_finished",
            batch_id=str(batch_id),
            drafted=drafted,
            draft_failed=draft_failed,
            enrolled=enroll.get("enrolled"),
            sent=enroll.get("sent"),
            failed=enroll.get("failed"),
        )
        return {
            "status": "completed",
            "drafted": drafted,
            "draft_failed": draft_failed,
            "enrolled": enroll.get("enrolled", 0),
            "sent": enroll.get("sent", 0),
            "failed": enroll.get("failed", 0),
            "email_setup_id": str(setup.id),
            "campaign_id": str(campaign.id),
        }

    async def _resolve_email_setup(self, batch: SearchBatch):
        if batch.email_setup_id is not None:
            setup = await self.email_setups.get_by_id(batch.email_setup_id)
            if setup is not None:
                return setup
        setups = await self.email_setups.list_all()
        if not setups:
            return None
        for setup in setups:
            if setup.is_default:
                return setup
        return setups[0]

    async def _ensure_campaign(
        self,
        *,
        workspace_id: uuid.UUID,
        batch: SearchBatch,
        setup_email: str,
        setup_name: str | None,
    ):
        if batch.outreach_campaign_id is not None:
            existing = await self.campaigns.get_by_id(workspace_id, batch.outreach_campaign_id)
            if existing is not None:
                return existing

        campaign = self.campaigns.create(
            workspace_id=workspace_id,
            name=f"Batch {batch.sequence:02d} auto outreach",
            status=CampaignStatus.DRAFT,
            from_email=setup_email,
            from_name=setup_name,
            daily_limit=200,
            timezone="UTC",
        )
        self.campaigns.add_step(
            campaign_id=campaign.id,
            step_number=1,
            delay_days=0,
            subject=_DEFAULT_STEP_SUBJECT,
            body=_DEFAULT_STEP_BODY,
            active=True,
        )
        await self.session.flush()
        return campaign


async def qualify_then_outreach_in_background(
    *,
    workspace_id: uuid.UUID,
    contact_ids: list[uuid.UUID],
    batch_id: uuid.UUID | None,
    settings: Settings,
) -> None:
    """Qualify leads, then (when a batch id is known) auto-draft and send."""
    from app.services.lead_qualification_service import LeadQualificationService

    async with AsyncSessionLocal() as session:
        contacts_result = await session.execute(select(Contact).where(Contact.id.in_(contact_ids)))
        contacts = list(contacts_result.scalars().all())
        if contacts:
            qualification_service = LeadQualificationService(session, settings)
            result = await qualification_service.qualify_many(
                workspace_id=workspace_id, contacts=contacts
            )
            logger.info(
                "background_qualification_finished",
                workspace_id=str(workspace_id),
                qualified=result.qualified,
                skipped=result.skipped,
                failed=result.failed,
                total=result.total,
            )

    if batch_id is None:
        return

    async with AsyncSessionLocal() as session:
        try:
            summary = await BatchOutreachService(session, settings).run(
                workspace_id=workspace_id, batch_id=batch_id
            )
            logger.info("background_batch_outreach_finished", **{k: v for k, v in summary.items()})
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "background_batch_outreach_failed",
                batch_id=str(batch_id),
                error=str(exc),
            )
            batch = await SearchBatchRepository(session).get_by_id(workspace_id, batch_id)
            if batch is not None:
                batch.outreach_status = "failed"
                await session.commit()
