import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_workspace_member
from app.core.config import Settings, get_settings
from app.models.email_event import EmailEventType
from app.models.user import User
from app.providers.base import ProviderCategory
from app.repositories.ai_generation_repository import AIGenerationRepository
from app.repositories.search_batch_repository import SearchBatchRepository
from app.schemas.search_batch import (
    BatchPhoneEnrichResponse,
    BatchQualifyResponse,
    BatchRevealResponse,
    SearchBatchCreate,
    SearchBatchDetail,
    SearchBatchRead,
)
from app.services.batch_outreach_service import draft_batch_in_background
from app.services.phone_enrichment_service import PhoneEnrichmentService
from app.services.search_service import qualify_contacts_in_background, reveal_contacts_in_background

router = APIRouter(prefix="/search-batches", tags=["search-batches"])


@router.get("", response_model=list[SearchBatchRead])
async def list_search_batches(
    workspace_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = SearchBatchRepository(session)
    return await repo.list_for_workspace(workspace_id, limit=limit, offset=offset)


@router.post("", response_model=SearchBatchRead, status_code=status.HTTP_201_CREATED)
async def create_search_batch(
    payload: SearchBatchCreate,
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Create an empty named batch (for CSV import / later enrichment)."""
    repo = SearchBatchRepository(session)
    batch = await repo.create(
        workspace_id=workspace_id,
        provider="manual",
        category=ProviderCategory.PERSON_DISCOVERY,
        criteria_snapshot={"source": "manual_create"},
        created_by=current_user.id,
        name=payload.name.strip(),
    )
    await session.commit()
    await session.refresh(batch)
    return batch


@router.get("/{batch_id}", response_model=SearchBatchDetail)
async def get_search_batch(
    batch_id: uuid.UUID,
    workspace_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    repo = SearchBatchRepository(session)
    batch = await repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")
    contacts = await repo.list_contacts(batch_id)

    # Backfill drafts for older batches (or failed jobs) that never got them.
    # Only when idle/failed/skipped — avoid re-queuing on every poll for batches
    # already marked ready/completed.
    if batch.outreach_status in ("idle", "failed", "skipped"):
        with_email = [c for c in contacts if (c.email or "").strip()]
        if with_email:
            generations = AIGenerationRepository(session)
            needs_draft = False
            for contact in with_email:
                existing = await generations.list_for_contact(workspace_id, contact.id)
                if not existing:
                    needs_draft = True
                    break
            if needs_draft:
                background_tasks.add_task(
                    draft_batch_in_background,
                    workspace_id=workspace_id,
                    batch_id=batch_id,
                    settings=settings,
                )

    event_counts = await repo.email_event_counts(batch_id)
    sent = event_counts.get(EmailEventType.SENT, 0)
    bounced = event_counts.get(EmailEventType.BOUNCED, 0)
    rejected = event_counts.get(EmailEventType.FAILED, 0)

    return SearchBatchDetail(
        **SearchBatchRead.model_validate(batch).model_dump(),
        contacts=contacts,
        emails_sent=sent,
        bounced=bounced,
        rejected=rejected,
        bounce_rate=round(bounced / sent, 4) if sent else None,
        rejection_rate=round(rejected / (sent + rejected), 4) if (sent + rejected) else None,
    )


@router.post("/{batch_id}/qualify-all", response_model=BatchQualifyResponse)
async def qualify_all_in_batch(
    batch_id: uuid.UUID,
    workspace_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Schedules scoring for every not-yet-scored contact in this batch as
    a background task, rather than awaiting it inline — a real qualify()
    call takes 30-40+ seconds each, so a 25-lead batch can take 15+
    minutes; holding the HTTP connection open that long risks the
    ngrok tunnel/browser timing out well before the server finishes, which
    then looks like a failure and invites a second click that starts a
    genuinely concurrent second run on the same batch (LeadQualificationService's
    in-progress guard prevents that from double-scoring the same contact,
    but it's still wasted server time better avoided). Skips contacts that
    already have a qualification — re-running this after a partial
    completion or after adding more leads only schedules what's still
    missing. Scores land on the batch page's existing polling as they
    finish; this response only reports what got scheduled."""
    batch_repo = SearchBatchRepository(session)
    batch = await batch_repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")

    contacts = await batch_repo.list_contacts(batch_id)
    to_score = [c for c in contacts if c.latest_qualification is None]
    if to_score:
        background_tasks.add_task(
            qualify_contacts_in_background,
            workspace_id=workspace_id,
            contact_ids=[c.id for c in to_score],
            settings=settings,
        )
    return BatchQualifyResponse(
        scheduled=len(to_score), already_scored=len(contacts) - len(to_score), total=len(contacts)
    )


@router.post("/{batch_id}/reveal-all", response_model=BatchRevealResponse)
async def reveal_all_in_batch(
    batch_id: uuid.UUID,
    workspace_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Manual recovery action for when automatic post-search reveal was
    interrupted (server restart, network blip) partway through a batch —
    schedules reveal for every not-yet-revealed contact as a background
    task, rather than awaiting it inline: a real reveal() call is a live
    Apollo/Smartlead API request per contact, and a full batch's worth
    sequentially (measured: 72s for 100 contacts) risks the ngrok tunnel/
    proxy timing out well before the server finishes — which then looks
    like a failure and invites a second click on a batch that's actually
    still working. Skips contacts that already have an email or already
    had a reveal attempted — re-running this after a partial completion
    only schedules what's still missing. Emails land on the batch page's
    existing polling as they finish; this response only reports what got
    scheduled."""
    batch_repo = SearchBatchRepository(session)
    batch = await batch_repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")

    contacts = await batch_repo.list_contacts(batch_id)
    to_reveal = [c for c in contacts if c.revealable]
    if to_reveal:
        background_tasks.add_task(
            reveal_contacts_in_background,
            workspace_id=workspace_id,
            contact_ids=[c.id for c in to_reveal],
            provider=batch.provider,
            settings=settings,
        )
    return BatchRevealResponse(
        scheduled=len(to_reveal), already_revealed=len(contacts) - len(to_reveal), total=len(contacts)
    )


@router.post("/{batch_id}/enrich-phones", response_model=BatchPhoneEnrichResponse)
async def enrich_phones_in_batch(
    batch_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Apollo only, manual/on-demand only — never automatic, since phone
    reveal costs extra credits (8 per mobile number found) on top of the
    email reveal that already runs automatically. Requests an async phone
    lookup for every contact in this batch that doesn't have one yet;
    Apollo delivers the actual number later via webhook (see
    app/api/v1/webhooks.py's /apollo/phone-reveal), not in this response —
    poll/refresh the batch to see numbers land, same as scoring."""
    batch_repo = SearchBatchRepository(session)
    batch = await batch_repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")
    if batch.provider != "apollo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone enrichment is only available for Apollo-sourced batches",
        )
    if not settings.PUBLIC_BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Phone enrichment is not configured (set PUBLIC_BASE_URL — Apollo must be able "
            "to reach this server from the internet to deliver phone numbers).",
        )

    webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/webhooks/apollo/phone-reveal"
    if settings.APOLLO_WEBHOOK_SECRET:
        webhook_url += f"?secret={settings.APOLLO_WEBHOOK_SECRET}"

    contacts = await batch_repo.list_contacts(batch_id)
    service = PhoneEnrichmentService(session, settings)
    result = await service.request_many(
        workspace_id=workspace_id, contacts=contacts, provider=batch.provider, webhook_url=webhook_url
    )
    return BatchPhoneEnrichResponse(
        requested=result.requested, skipped=result.skipped, failed=result.failed, total=result.total
    )
