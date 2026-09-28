"""Pre-generate AI drafts for a search batch after Discover / CSV import.

Sending is owned by Start Campaign (paced enroll). This job only drafts
so drafts are ready before send. Skips when the batch has no emails.

Drafts run independently of scoring — they must not wait for every lead
to finish qualification (that can take many minutes on a full batch).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import AsyncSessionLocal
from app.models.contact import Contact
from app.repositories.ai_generation_repository import AIGenerationRepository
from app.repositories.email_setup_repository import EmailSetupRepository
from app.repositories.search_batch_repository import SearchBatchRepository
from app.services.personalization_service import PersonalizationService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BatchOutreachService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.batches = SearchBatchRepository(session)
        self.email_setups = EmailSetupRepository(session)
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
        if setup is not None:
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

        batch.outreach_status = "ready" if drafted else "failed"
        await self.session.commit()

        logger.info(
            "batch_outreach_drafts_finished",
            batch_id=str(batch_id),
            drafted=drafted,
            draft_failed=draft_failed,
        )
        return {
            "status": batch.outreach_status,
            "drafted": drafted,
            "draft_failed": draft_failed,
            "sent": 0,
            "email_setup_id": str(setup.id) if setup else None,
        }

    async def _resolve_email_setup(self, batch):
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


async def draft_batch_in_background(
    *,
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
    settings: Settings,
) -> None:
    """Pre-generate AI email drafts for every emailed lead in the batch.

    Scheduled as soon as a batch is created (Discover search or CSV import)
    so drafts do not wait on the slow score-all loop.
    """
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


async def qualify_then_outreach_in_background(
    *,
    workspace_id: uuid.UUID,
    contact_ids: list[uuid.UUID],
    batch_id: uuid.UUID | None,
    settings: Settings,
) -> None:
    """Qualify leads, then (when a batch id is known) pre-generate drafts.

    Prefer scheduling `draft_batch_in_background` separately so drafts start
    immediately; this combined path remains for callers that still use it.
    """
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

    await draft_batch_in_background(
        workspace_id=workspace_id, batch_id=batch_id, settings=settings
    )
