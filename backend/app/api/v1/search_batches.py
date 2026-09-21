import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_member
from app.repositories.search_batch_repository import SearchBatchRepository
from app.schemas.search_batch import SearchBatchDetail, SearchBatchRead

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
