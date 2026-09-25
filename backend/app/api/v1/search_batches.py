import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_member
from app.core.config import Settings, get_settings
from app.repositories.search_batch_repository import SearchBatchRepository
from app.schemas.search_batch import (
    BatchQualifyResponse,
    BatchRevealResponse,
    SearchBatchDetail,
    SearchBatchRead,
)
from app.services.lead_reveal_service import LeadRevealService
from app.services.search_service import qualify_contacts_in_background

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


@router.get("/{batch_id}", response_model=SearchBatchDetail)
async def get_search_batch(
    batch_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = SearchBatchRepository(session)
    batch = await repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")
    contacts = await repo.list_contacts(batch_id)
    return SearchBatchDetail(**SearchBatchRead.model_validate(batch).model_dump(), contacts=contacts)


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
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Manual recovery action for when automatic post-search reveal was
    interrupted (server restart, network blip) partway through a batch —
    reveals every not-yet-revealed contact in this batch. Reuses
    reveal_many's own guards (already has email, already attempted) so
    re-running this after a partial failure only touches what's still
    missing, never re-billing a contact that was already revealed."""
    batch_repo = SearchBatchRepository(session)
    batch = await batch_repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")

    contacts = await batch_repo.list_contacts(batch_id)
    service = LeadRevealService(session, settings)
    result = await service.reveal_many(workspace_id=workspace_id, contacts=contacts, provider=batch.provider)
    return BatchRevealResponse(
        revealed=result.revealed, skipped=result.skipped, failed=result.failed, total=result.total
    )
