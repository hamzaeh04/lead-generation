import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services.lead_qualification_service import LeadQualificationService
from app.services.lead_reveal_service import LeadRevealService

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
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Scores every not-yet-scored contact in this batch. Skips contacts
    that already have a qualification — re-running this after a partial
    failure or after adding more leads only scores what's new, rather
    than re-billing every lead on every click."""
    batch_repo = SearchBatchRepository(session)
    batch = await batch_repo.get_by_id(workspace_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search batch not found")

    contacts = await batch_repo.list_contacts(batch_id)
    service = LeadQualificationService(session, settings)
    result = await service.qualify_many(workspace_id=workspace_id, contacts=contacts)
    return BatchQualifyResponse(
        qualified=result.qualified, skipped=result.skipped, failed=result.failed, total=result.total
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
