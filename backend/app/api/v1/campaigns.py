import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_editor, require_workspace_member
from app.core.config import Settings, get_settings
from app.models.campaign import CampaignStatus
from app.models.campaign_recipient import CampaignRecipient
from app.models.contact import Contact, LeadStatus
from app.models.email_event import EmailEvent, EmailEventType, ReplySentiment
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.intent_signal_repository import IntentSignalRepository
from app.schemas.campaign import (
    CampaignCreate,
    CampaignRead,
    CampaignReport,
    CampaignStepCreate,
    CampaignStepRead,
    CampaignStepUpdate,
    EnrollRequest,
    EnrollResponse,
    PreviewRequest,
    PreviewResponse,
    ProcessCampaignResponse,
)
from app.services.campaign_sending_service import CampaignSendingService
from app.services.campaign_service import CampaignService
from app.services.template_service import build_context, render_template
from app.services.unsubscribe_token_service import create_unsubscribe_token

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignRead, status_code=201)
async def create_campaign(
    workspace_id: uuid.UUID,
    payload: CampaignCreate,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CampaignRepository(session)
    campaign = repo.create(workspace_id=workspace_id, **payload.model_dump())
    await session.commit()
    await session.refresh(campaign)
    # A freshly-created campaign has no steps yet; skip touching the
    # unloaded relationship (would trigger a lazy-load outside async
    # context) and construct the response explicitly instead.
    return CampaignRead(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        from_name=campaign.from_name,
        from_email=campaign.from_email,
        reply_to=campaign.reply_to,
        daily_limit=campaign.daily_limit,
        timezone=campaign.timezone,
        steps=[],
    )


@router.get("", response_model=list[CampaignRead])
async def list_campaigns(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    return await CampaignRepository(session).list_for_workspace(workspace_id)


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    campaign = await CampaignRepository(session).get_by_id(workspace_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


@router.post("/{campaign_id}/steps", response_model=CampaignStepRead, status_code=201)
async def add_campaign_step(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: CampaignStepCreate,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CampaignRepository(session)
    campaign = await repo.get_by_id(workspace_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    existing = await repo.get_step(campaign_id, payload.step_number)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Step {payload.step_number} already exists")

    step = repo.add_step(campaign_id=campaign_id, **payload.model_dump())
    await session.commit()
    await session.refresh(step)
    return step


@router.patch("/{campaign_id}/steps/{step_id}", response_model=CampaignStepRead)
async def update_campaign_step(
    campaign_id: uuid.UUID,
    step_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: CampaignStepUpdate,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CampaignRepository(session)
    campaign = await repo.get_by_id(workspace_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    step = await repo.get_step_by_id(campaign_id, step_id)
    if step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Step not found")

    updates = payload.model_dump(exclude_unset=True)
    if "step_number" in updates and updates["step_number"] != step.step_number:
        existing = await repo.get_step(campaign_id, updates["step_number"])
        if existing is not None and existing.id != step.id:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Step {updates['step_number']} already exists")

    for field_name, value in updates.items():
        setattr(step, field_name, value)

    await session.commit()
    await session.refresh(step)
    return step


@router.delete("/{campaign_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign_step(
    campaign_id: uuid.UUID,
    step_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CampaignRepository(session)
    campaign = await repo.get_by_id(workspace_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    step = await repo.get_step_by_id(campaign_id, step_id)
    if step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Step not found")

    await repo.delete_step(step)
    await session.commit()
    # expire_on_commit=False means campaign.steps (already loaded above via
    # get_by_id's selectinload) keeps the now-deleted step in its in-memory
    # collection — expire it so the next read re-queries from the DB.
    session.expire(campaign, ["steps"])


@router.post("/{campaign_id}/enroll", response_model=EnrollResponse)
async def enroll_contacts(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: EnrollRequest,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = CampaignService(session)
    return await service.enroll_contacts(
        workspace_id=workspace_id, campaign_id=campaign_id, contact_ids=payload.contact_ids
    )


@router.post("/{campaign_id}/start", response_model=CampaignRead)
async def start_campaign(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = CampaignService(session)
    return await service.set_status(
        workspace_id=workspace_id, campaign_id=campaign_id, target=CampaignStatus.RUNNING
    )


@router.post("/{campaign_id}/pause", response_model=CampaignRead)
async def pause_campaign(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = CampaignService(session)
    return await service.set_status(
        workspace_id=workspace_id, campaign_id=campaign_id, target=CampaignStatus.PAUSED
    )


@router.post("/{campaign_id}/resume", response_model=CampaignRead)
async def resume_campaign(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = CampaignService(session)
    return await service.set_status(
        workspace_id=workspace_id, campaign_id=campaign_id, target=CampaignStatus.RUNNING
    )


@router.post("/{campaign_id}/cancel", response_model=CampaignRead)
async def cancel_campaign(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = CampaignService(session)
    return await service.set_status(
        workspace_id=workspace_id, campaign_id=campaign_id, target=CampaignStatus.CANCELLED
    )


@router.post("/{campaign_id}/process", response_model=ProcessCampaignResponse)
async def process_campaign_now(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Manually triggers one processing pass for due sends. In production
    this same logic also runs periodically via Celery beat
    (app/tasks/campaign_tasks.py) — this endpoint exists so a run doesn't
    require a live worker to test or to force an out-of-cycle send."""
    service = CampaignSendingService(session, settings)
    return await service.process_campaign(workspace_id=workspace_id, campaign_id=campaign_id)


@router.post("/{campaign_id}/preview", response_model=PreviewResponse)
async def preview_campaign_step(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: PreviewRequest,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get_by_id(workspace_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    step = await campaign_repo.get_step(campaign_id, payload.step_number)
    if step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Step not found")

    contact = await ContactRepository(session).get_by_id(workspace_id, payload.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")

    company = None
    if contact.company_id is not None:
        company = await CompanyRepository(session).get_by_id(workspace_id, contact.company_id)

    latest_signal = None
    if company is not None:
        signals = await IntentSignalRepository(session).list_for_company(workspace_id, company.id)
        latest_signal = signals[0] if signals else None

    unsubscribe_url = f"/unsubscribe/{create_unsubscribe_token(workspace_id=workspace_id, contact_id=contact.id)}"
    context = build_context(
        contact=contact, company=company, personalization=None,
        unsubscribe_url=unsubscribe_url, intent_signal=latest_signal,
    )
    subject_rendered = render_template(step.subject, context)
    body_rendered = render_template(step.body, context)

    return PreviewResponse(
        subject=subject_rendered.text,
        body=body_rendered.text,
        variables_filled=sorted(set(subject_rendered.variables_filled + body_rendered.variables_filled)),
        variables_empty=sorted(set(subject_rendered.variables_empty + body_rendered.variables_empty)),
        unrecognized_variables=sorted(
            set(subject_rendered.unrecognized_variables + body_rendered.unrecognized_variables)
        ),
    )


@router.get("/{campaign_id}/report", response_model=CampaignReport)
async def get_campaign_report(
    campaign_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Client-ready report (section 49) computed entirely from real
    EmailEvent/CampaignRecipient/Contact rows — never estimated."""
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get_by_id(workspace_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    contacts_enrolled = (
        await session.execute(
            select(func.count()).select_from(CampaignRecipient).where(
                CampaignRecipient.campaign_id == campaign_id
            )
        )
    ).scalar_one()

    event_counts = dict(
        (
            await session.execute(
                select(EmailEvent.event_type, func.count())
                .join(CampaignRecipient, EmailEvent.campaign_recipient_id == CampaignRecipient.id)
                .where(CampaignRecipient.campaign_id == campaign_id)
                .group_by(EmailEvent.event_type)
            )
        ).all()
    )
    sent = event_counts.get(EmailEventType.SENT, 0)
    bounced = event_counts.get(EmailEventType.BOUNCED, 0)
    opened = event_counts.get(EmailEventType.OPENED, 0)
    clicked = event_counts.get(EmailEventType.CLICKED, 0)
    replied = event_counts.get(EmailEventType.REPLIED, 0)
    unsubscribed = event_counts.get(EmailEventType.UNSUBSCRIBED, 0)
    delivered = max(sent - bounced, 0)

    positive_replies = (
        await session.execute(
            select(func.count()).select_from(EmailEvent).join(
                CampaignRecipient, EmailEvent.campaign_recipient_id == CampaignRecipient.id
            ).where(
                CampaignRecipient.campaign_id == campaign_id,
                EmailEvent.event_type == EmailEventType.REPLIED,
                EmailEvent.reply_sentiment == ReplySentiment.POSITIVE,
            )
        )
    ).scalar_one()

    status_counts = dict(
        (
            await session.execute(
                select(Contact.status, func.count())
                .join(CampaignRecipient, CampaignRecipient.contact_id == Contact.id)
                .where(CampaignRecipient.campaign_id == campaign_id)
                .group_by(Contact.status)
            )
        ).all()
    )

    return CampaignReport(
        campaign_id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        contacts_enrolled=contacts_enrolled,
        sent=sent,
        delivered=delivered,
        opened=opened,
        clicked=clicked,
        replied=replied,
        positive_replies=positive_replies,
        bounced=bounced,
        unsubscribed=unsubscribed,
        meetings=status_counts.get(LeadStatus.MEETING, 0),
        won=status_counts.get(LeadStatus.WON, 0),
        delivery_rate=round(delivered / sent, 4) if sent else None,
        bounce_rate=round(bounced / sent, 4) if sent else None,
        open_rate=round(opened / sent, 4) if sent else None,
        click_rate=round(clicked / sent, 4) if sent else None,
        reply_rate=round(replied / sent, 4) if sent else None,
        positive_reply_rate=round(positive_replies / replied, 4) if replied else None,
    )
