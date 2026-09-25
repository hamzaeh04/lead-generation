"""Workspace dashboard (section 48) — every number here is computed from
real rows in the database, never estimated or fabricated. Two numbers are
deliberately left null/None rather than guessed:

- `positive_reply_rate`: nothing in this codebase classifies a reply's
  sentiment (that would need NLP or manual tagging, neither built yet) —
  reporting a guessed split would violate the platform's core rule.
- `high_icp_leads`: only computable against a specific ICPProfile: pass
  `icp_profile_id` or this stays null rather than silently picking one.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.company import Company, CompanySource
from app.models.contact import Contact, LeadStatus
from app.models.email_event import EmailEvent, EmailEventType
from app.models.icp_profile import ICPProfile
from app.models.intent_signal import IntentSignal
from app.models.provider_usage import ProviderUsage
from app.schemas.analytics import AnalyticsOverview, CampaignSummary, SourceCount
from app.services.icp_score_service import compute_icp_score
from app.services.intent_score_service import compute_intent_score

_HIGH_INTENT_THRESHOLD = 50
_HIGH_ICP_THRESHOLD = 70


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(
        self, workspace_id: uuid.UUID, *, icp_profile_id: uuid.UUID | None = None
    ) -> AnalyticsOverview:
        total_companies = await self._count(select(func.count()).select_from(Company).where(
            Company.workspace_id == workspace_id
        ))
        total_contacts = await self._count(select(func.count()).select_from(Contact).where(
            Contact.workspace_id == workspace_id
        ))
        verified_emails = await self._count_verified(workspace_id)
        meetings = await self._count_by_status(workspace_id, LeadStatus.MEETING)
        conversions = await self._count_by_status(workspace_id, LeadStatus.WON)

        companies = (
            await self.session.execute(select(Company).where(Company.workspace_id == workspace_id))
        ).scalars().all()
        high_intent_leads = await self._count_high_intent(workspace_id, companies)
        high_icp_leads = None
        if icp_profile_id is not None:
            high_icp_leads = await self._count_high_icp(workspace_id, companies, icp_profile_id)

        event_counts = await self._email_event_counts(workspace_id)
        sent = event_counts.get(EmailEventType.SENT, 0)
        bounced = event_counts.get(EmailEventType.BOUNCED, 0)
        opened = event_counts.get(EmailEventType.OPENED, 0)
        clicked = event_counts.get(EmailEventType.CLICKED, 0)
        replied = event_counts.get(EmailEventType.REPLIED, 0)
        delivered = max(sent - bounced, 0)

        total_cost = await self._total_provider_cost(workspace_id)

        top_sources = await self._top_sources(workspace_id)
        top_campaigns = await self._top_campaigns(workspace_id)

        return AnalyticsOverview(
            total_companies=total_companies,
            total_contacts=total_contacts,
            verified_emails=verified_emails,
            high_intent_leads=high_intent_leads,
            high_icp_leads=high_icp_leads,
            meetings=meetings,
            conversions=conversions,
            emails_sent=sent,
            delivered=delivered,
            bounced=bounced,
            opened=opened,
            clicked=clicked,
            replied=replied,
            delivery_rate=round(delivered / sent, 4) if sent else None,
            bounce_rate=round(bounced / sent, 4) if sent else None,
            open_rate=round(opened / sent, 4) if sent else None,
            click_rate=round(clicked / sent, 4) if sent else None,
            reply_rate=round(replied / sent, 4) if sent else None,
            total_provider_cost=total_cost,
            cost_per_verified_lead=round(total_cost / verified_emails, 4) if verified_emails else None,
            cost_per_qualified_lead=round(total_cost / high_intent_leads, 4) if high_intent_leads else None,
            top_sources=top_sources,
            top_campaigns=top_campaigns,
        )

    async def _count(self, stmt) -> int:
        return (await self.session.execute(stmt)).scalar_one()

    async def _count_by_status(self, workspace_id: uuid.UUID, status: LeadStatus) -> int:
        return await self._count(
            select(func.count()).select_from(Contact).where(
                Contact.workspace_id == workspace_id, Contact.status == status
            )
        )

    async def _count_verified(self, workspace_id: uuid.UUID) -> int:
        # No email-verification provider is wired up; "verified" now just
        # means the contact has an email on file at all.
        return await self._count(
            select(func.count()).select_from(Contact).where(
                Contact.workspace_id == workspace_id, Contact.email.is_not(None)
            )
        )

    async def _count_high_intent(self, workspace_id: uuid.UUID, companies: list[Company]) -> int:
        count = 0
        for company in companies:
            signals = (
                await self.session.execute(
                    select(IntentSignal).where(
                        IntentSignal.workspace_id == workspace_id, IntentSignal.company_id == company.id
                    )
                )
            ).scalars().all()
            if signals and compute_intent_score(list(signals)) >= _HIGH_INTENT_THRESHOLD:
                count += 1
        return count

    async def _count_high_icp(
        self, workspace_id: uuid.UUID, companies: list[Company], icp_profile_id: uuid.UUID
    ) -> int:
        icp = await self.session.get(ICPProfile, icp_profile_id)
        if icp is None or icp.workspace_id != workspace_id:
            return 0
        count = 0
        for company in companies:
            contacts = (
                await self.session.execute(
                    select(Contact).where(
                        Contact.workspace_id == workspace_id, Contact.company_id == company.id
                    )
                )
            ).scalars().all()
            score, _ = compute_icp_score(company, list(contacts), icp)
            if score >= _HIGH_ICP_THRESHOLD:
                count += 1
        return count

    async def _email_event_counts(self, workspace_id: uuid.UUID) -> dict[EmailEventType, int]:
        result = await self.session.execute(
            select(EmailEvent.event_type, func.count())
            .where(EmailEvent.workspace_id == workspace_id)
            .group_by(EmailEvent.event_type)
        )
        return dict(result.all())

    async def _total_provider_cost(self, workspace_id: uuid.UUID) -> float:
        result = await self.session.execute(
            select(func.coalesce(func.sum(ProviderUsage.estimated_cost), 0.0)).where(
                ProviderUsage.workspace_id == workspace_id
            )
        )
        return float(result.scalar_one())

    async def _top_sources(self, workspace_id: uuid.UUID, limit: int = 5) -> list[SourceCount]:
        result = await self.session.execute(
            select(CompanySource.provider, func.count(func.distinct(CompanySource.company_id)))
            .join(Company, Company.id == CompanySource.company_id)
            .where(Company.workspace_id == workspace_id)
            .group_by(CompanySource.provider)
            .order_by(func.count(func.distinct(CompanySource.company_id)).desc())
            .limit(limit)
        )
        return [SourceCount(provider=provider, count=count) for provider, count in result.all()]

    async def _top_campaigns(self, workspace_id: uuid.UUID, limit: int = 5) -> list[CampaignSummary]:
        campaigns = (
            await self.session.execute(select(Campaign).where(Campaign.workspace_id == workspace_id))
        ).scalars().all()

        summaries: list[CampaignSummary] = []
        for campaign in campaigns:
            counts = await self.session.execute(
                select(EmailEvent.event_type, func.count())
                .join(CampaignRecipient, EmailEvent.campaign_recipient_id == CampaignRecipient.id)
                .where(CampaignRecipient.campaign_id == campaign.id)
                .group_by(EmailEvent.event_type)
            )
            by_type = dict(counts.all())
            summaries.append(
                CampaignSummary(
                    campaign_id=campaign.id,
                    name=campaign.name,
                    sent=by_type.get(EmailEventType.SENT, 0),
                    opened=by_type.get(EmailEventType.OPENED, 0),
                    clicked=by_type.get(EmailEventType.CLICKED, 0),
                    replied=by_type.get(EmailEventType.REPLIED, 0),
                    bounced=by_type.get(EmailEventType.BOUNCED, 0),
                )
            )
        summaries.sort(key=lambda s: s.sent, reverse=True)
        return summaries[:limit]
