"""Campaign lifecycle: creation, steps, enrollment, start/pause/resume."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.campaign import Campaign, CampaignStatus
from app.repositories.campaign_recipient_repository import CampaignRecipientRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.email_setup_repository import EmailSetupRepository
from app.repositories.search_batch_repository import SearchBatchRepository
from app.services.campaign_sending_service import CampaignSendingService


class CampaignService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings
        self.campaigns = CampaignRepository(session)
        self.recipients = CampaignRecipientRepository(session)
        self.contacts = ContactRepository(session)
        self.batches = SearchBatchRepository(session)
        self.email_setups = EmailSetupRepository(session)

    async def enroll_contacts(
        self,
        *,
        workspace_id: uuid.UUID,
        campaign_id: uuid.UUID,
        contact_ids: list[uuid.UUID] | None = None,
        batch_ids: list[uuid.UUID] | None = None,
        email_setup_id: uuid.UUID | None = None,
        subject: str | None = None,
        body: str | None = None,
    ) -> dict:
        campaign = await self.campaigns.get_by_id(workspace_id, campaign_id)
        if campaign is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

        if batch_ids and email_setup_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "email_setup_id is required when enrolling batches so mail can be sent from that SMTP account",
            )

        if (subject is None) ^ (body is None):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Provide both subject and body together (from Sequence steps)",
            )

        if subject is not None and body is not None:
            await self._upsert_step_one(campaign_id=campaign.id, subject=subject.strip(), body=body.strip())
            campaign = await self.campaigns.get_by_id(workspace_id, campaign_id)
            if campaign is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

        if email_setup_id is not None:
            setup = await self.email_setups.get_by_id(email_setup_id)
            if setup is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
            if not campaign.steps and subject is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Campaign has no steps — add subject and body in Sequence steps before enrolling to send.",
                )
            campaign.from_email = setup.smtp_email
            if not campaign.from_name:
                campaign.from_name = setup.name

        resolved: list[uuid.UUID] = list(contact_ids or [])
        for batch_id in batch_ids or []:
            batch = await self.batches.get_by_id(workspace_id, batch_id)
            if batch is None:
                continue
            for contact_id in await self.batches.list_contact_ids(batch_id):
                resolved.append(contact_id)

        seen: set[uuid.UUID] = set()
        unique_ids: list[uuid.UUID] = []
        for contact_id in resolved:
            if contact_id in seen:
                continue
            seen.add(contact_id)
            unique_ids.append(contact_id)

        if not unique_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Provide at least one contact_id or batch_id to enroll",
            )

        enrolled = already_enrolled = not_found = 0
        now = datetime.now(timezone.utc)
        newly_enrolled_contacts: list = []

        for contact_id in unique_ids:
            contact = await self.contacts.get_by_id(workspace_id, contact_id)
            if contact is None:
                not_found += 1
                continue
            existing = await self.recipients.find(campaign_id, contact_id)
            if existing is not None:
                already_enrolled += 1
                continue
            self.recipients.create(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                contact_id=contact_id,
                next_send_at=now,
            )
            newly_enrolled_contacts.append(contact)
            enrolled += 1

        await self.session.commit()
        # contact.campaign_recipients was eager-loaded above (empty, since
        # the just-created recipient row didn't exist yet) and
        # expire_on_commit=False means it won't auto-refresh on its own —
        # expire it so the next read (e.g. email_track_status) sees the
        # new recipient instead of a stale empty collection. Same pattern
        # as the "steps" expire in delete_step, for the same reason.
        for contact in newly_enrolled_contacts:
            self.session.expire(contact, ["campaign_recipients"])

        result = {
            "enrolled": enrolled,
            "already_enrolled": already_enrolled,
            "not_found": not_found,
            "sent": 0,
            "failed": 0,
            "suppressed": 0,
        }

        # When an Email Setup is provided, start (if needed) and send immediately
        # from that SMTP account using the sequence subject/body.
        if email_setup_id is not None and self.settings is not None:
            if campaign.status in (CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.PAUSED):
                campaign.status = CampaignStatus.RUNNING
                await self.session.commit()

            send_summary = await CampaignSendingService(self.session, self.settings).process_campaign(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                email_setup_id=email_setup_id,
                batch_size=max(len(unique_ids), 50),
                immediate=True,
            )
            result["sent"] = send_summary.get("sent", 0)
            result["failed"] = send_summary.get("failed", 0)
            result["suppressed"] = send_summary.get("suppressed", 0)

        return result

    async def _upsert_step_one(self, *, campaign_id: uuid.UUID, subject: str, body: str) -> None:
        """Create or update step 1 with the Sequence subject/body from the enroll payload."""
        step = await self.campaigns.get_step(campaign_id, 1)
        if step is None:
            self.campaigns.add_step(
                campaign_id=campaign_id,
                step_number=1,
                delay_days=0,
                subject=subject,
                body=body,
                active=True,
            )
        else:
            step.subject = subject
            step.body = body
        await self.session.flush()

    async def set_status(
        self, *, workspace_id: uuid.UUID, campaign_id: uuid.UUID, target: CampaignStatus
    ) -> Campaign:
        campaign = await self.campaigns.get_by_id(workspace_id, campaign_id)
        if campaign is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

        allowed_transitions: dict[CampaignStatus, set[CampaignStatus]] = {
            CampaignStatus.RUNNING: {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.PAUSED},
            CampaignStatus.PAUSED: {CampaignStatus.RUNNING},
            CampaignStatus.CANCELLED: {
                CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.RUNNING, CampaignStatus.PAUSED,
            },
        }
        if campaign.status not in allowed_transitions.get(target, set()):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot move campaign from '{campaign.status}' to '{target}'.",
            )

        if target == CampaignStatus.RUNNING and not campaign.steps:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Campaign has no steps — add at least one before starting."
            )

        campaign.status = target
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign
