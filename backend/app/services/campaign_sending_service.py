"""Processes due sends for one campaign: suppression check -> template
render -> send -> record event -> advance to the next step or complete.

Sender resolution order:
1. Explicit `email_setup_id` (enroll-and-send path)
2. EmailSetup whose smtp_email matches the campaign's from_email
3. Highest-priority enabled email_sender provider from the registry

One sender is selected once per run rather than re-resolved per recipient.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, RecipientStatus
from app.models.contact import LeadStatus
from app.models.email_event import EmailEventType
from app.models.email_setup import EmailSetup
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.email_senders.base import OutboundEmail, SendStatus
from app.providers.email_senders.smtp_provider import SMTPEmailSenderProvider
from app.repositories.ai_generation_repository import AIGenerationRepository
from app.repositories.campaign_recipient_repository import CampaignRecipientRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.email_event_repository import EmailEventRepository
from app.repositories.email_setup_repository import EmailSetupRepository
from app.repositories.intent_signal_repository import IntentSignalRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.services.suppression_service import SuppressionService
from app.services.template_service import build_context, ensure_lead_personalization, render_template
from app.services.unsubscribe_token_service import create_unsubscribe_token
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _smtp_from_setup(setup: EmailSetup) -> SMTPEmailSenderProvider:
    return SMTPEmailSenderProvider(
        host=setup.smtp_host,
        port=setup.smtp_port,
        username=setup.smtp_email,
        password=setup.smtp_password,
        use_tls=setup.smtp_use_tls,
    )


class CampaignSendingService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.campaigns = CampaignRepository(session)
        self.recipients = CampaignRecipientRepository(session)
        self.contacts = ContactRepository(session)
        self.companies = CompanyRepository(session)
        self.intent_signals = IntentSignalRepository(session)
        self.generations = AIGenerationRepository(session)
        self.events = EmailEventRepository(session)
        self.provider_configs = ProviderConfigRepository(session)
        self.email_setups = EmailSetupRepository(session)
        self.suppressions = SuppressionService(session)

    async def process_campaign(
        self,
        *,
        workspace_id: uuid.UUID,
        campaign_id: uuid.UUID,
        batch_size: int = 50,
        email_setup_id: uuid.UUID | None = None,
        immediate: bool = False,
    ) -> dict:
        campaign = await self.campaigns.get_by_id(workspace_id, campaign_id)
        if campaign is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

        summary = {"sent": 0, "suppressed": 0, "completed": 0, "failed": 0, "skipped_no_quota": False}

        if campaign.status != CampaignStatus.RUNNING:
            return summary

        now = datetime.now(timezone.utc)
        if immediate:
            # Enroll-and-send: deliver every due recipient now, ignore daily_limit.
            remaining_quota = batch_size
        else:
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            sent_today = await self.recipients.count_sent_today(campaign_id, since=day_start)
            remaining_quota = max(campaign.daily_limit - sent_today, 0)
            if remaining_quota <= 0:
                summary["skipped_no_quota"] = True
                return summary

        provider, provider_name, setup = await self._resolve_sender(
            campaign=campaign, email_setup_id=email_setup_id
        )
        if setup is not None:
            campaign.from_email = setup.smtp_email
            if not campaign.from_name:
                campaign.from_name = setup.name

        due = await self.recipients.list_due(campaign_id, now=now, limit=min(remaining_quota, batch_size))
        for recipient in due:
            await self._process_recipient(
                campaign=campaign,
                recipient=recipient,
                provider=provider,
                provider_name=provider_name,
                now=now,
                summary=summary,
            )

        await self.session.commit()
        return summary

    async def _resolve_sender(
        self, *, campaign: Campaign, email_setup_id: uuid.UUID | None
    ) -> tuple[object, str, EmailSetup | None]:
        setup: EmailSetup | None = None
        if email_setup_id is not None:
            setup = await self.email_setups.get_by_id(email_setup_id)
            if setup is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
        else:
            setup = await self.email_setups.get_by_email(campaign.from_email)

        if setup is not None:
            return _smtp_from_setup(setup), "smtp", setup

        registry_entries = await self.provider_configs.list_enabled_for_category(
            ProviderCategory.EMAIL_SENDER
        )
        if not registry_entries:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No Email Setup matches this campaign's from_email and no email-sender provider is enabled",
            )

        provider = None
        provider_name = None
        for registry_entry in registry_entries:
            candidate = provider_factory.build_provider(
                registry_entry.provider, ProviderCategory.EMAIL_SENDER, self.settings
            )
            if candidate is not None:
                provider, provider_name = candidate, registry_entry.provider
                break
        if provider is None:
            env_var = provider_factory.required_env_var(
                registry_entries[0].provider, ProviderCategory.EMAIL_SENDER
            )
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"Provider '{registry_entries[0].provider}' credentials not configured (set {env_var}).",
            )
        return provider, provider_name, None

    async def _process_recipient(
        self,
        *,
        campaign: Campaign,
        recipient: CampaignRecipient,
        provider,
        provider_name: str,
        now: datetime,
        summary: dict,
    ) -> None:
        contact = await self.contacts.get_by_id(campaign.workspace_id, recipient.contact_id)
        if contact is None or not contact.email:
            recipient.status = RecipientStatus.FAILED
            summary["failed"] += 1
            return

        if await self.suppressions.is_suppressed(campaign.workspace_id, contact.email):
            recipient.status = RecipientStatus.SUPPRESSED
            summary["suppressed"] += 1
            return

        next_step_number = recipient.current_step_number + 1
        step = await self.campaigns.get_step(campaign.id, next_step_number)
        if step is None or not step.active:
            recipient.status = RecipientStatus.COMPLETED
            summary["completed"] += 1
            return

        company = None
        if contact.company_id is not None:
            company = await self.companies.get_by_id(campaign.workspace_id, contact.company_id)

        latest_signal = None
        if company is not None:
            signals = await self.intent_signals.list_for_company(campaign.workspace_id, company.id)
            latest_signal = signals[0] if signals else None

        generations = await self.generations.list_for_contact(campaign.workspace_id, contact.id)
        latest_personalization = generations[0] if generations else None

        unsubscribe_token = create_unsubscribe_token(workspace_id=campaign.workspace_id, contact_id=contact.id)
        unsubscribe_url = f"/unsubscribe/{unsubscribe_token}"

        context = build_context(
            contact=contact,
            company=company,
            personalization=latest_personalization,
            unsubscribe_url=unsubscribe_url,
            intent_signal=latest_signal,
        )
        # Fall back to full_name when first_name is blank so "Hi {{first_name}}" still greets.
        if not context.get("first_name") and contact.full_name:
            context["first_name"] = contact.full_name.split()[0]

        subject_tpl, body_tpl = ensure_lead_personalization(step.subject, step.body)
        rendered_subject = render_template(subject_tpl, context).text
        rendered_body = render_template(body_tpl, context).text

        message = OutboundEmail(
            to_email=contact.email,
            from_email=campaign.from_email,
            from_name=campaign.from_name,
            subject=rendered_subject,
            html_body=rendered_body,
            reply_to=campaign.reply_to,
            unsubscribe_url=unsubscribe_url,
        )

        try:
            async with ProviderUsageRecorder(
                self.session,
                provider=provider_name,
                category=ProviderCategory.EMAIL_SENDER,
                operation="send",
                workspace_id=campaign.workspace_id,
            ) as usage:
                result = await provider.send(message)
                usage.records_returned = 1 if result.status == SendStatus.SENT else 0
        except ProviderUnavailableError as exc:
            logger.warning("campaign_send_provider_unavailable", provider=provider_name, error=str(exc))
            recipient.status = RecipientStatus.FAILED
            summary["failed"] += 1
            return

        if result.status != SendStatus.SENT:
            recipient.status = RecipientStatus.FAILED
            summary["failed"] += 1
            self.events.create(
                workspace_id=campaign.workspace_id,
                campaign_recipient_id=recipient.id,
                event_type=EmailEventType.FAILED,
                raw_payload={"error": result.error},
                occurred_at=now,
            )
            return

        self.events.create(
            workspace_id=campaign.workspace_id,
            campaign_recipient_id=recipient.id,
            event_type=EmailEventType.SENT,
            raw_payload={"provider_message_id": result.provider_message_id},
            occurred_at=now,
        )
        # CRM pipeline: first successful send is meaningful progress for a
        # lead that hasn't been engaged with yet. Never downgrades a
        # further-along status (e.g. already REPLIED).
        if contact.status in (LeadStatus.NEW, LeadStatus.VERIFIED, LeadStatus.READY_FOR_OUTREACH):
            contact.status = LeadStatus.CONTACTED

        recipient.current_step_number = next_step_number
        next_next_step = await self.campaigns.get_step(campaign.id, next_step_number + 1)
        if next_next_step is not None:
            recipient.next_send_at = now + timedelta(days=next_next_step.delay_days)
            recipient.status = RecipientStatus.PENDING
        else:
            recipient.status = RecipientStatus.COMPLETED
            summary["completed"] += 1
        summary["sent"] += 1
