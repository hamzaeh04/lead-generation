import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_admin, require_workspace_member
from app.schemas.workspace_api_keys import (
    WorkspaceApiKeysDefaults,
    WorkspaceApiKeysRead,
    WorkspaceApiKeysUpsert,
)
from app.services.workspace_api_keys_service import WorkspaceApiKeysService, get_defaults, to_read

router = APIRouter(prefix="/workspace-api-keys", tags=["workspace-api-keys"])


@router.get("/defaults", response_model=WorkspaceApiKeysDefaults)
async def workspace_api_keys_defaults(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
):
    """Placeholder text for the settings form (mirrors .env key names)."""
    return get_defaults()


@router.get("", response_model=WorkspaceApiKeysRead | None)
async def get_workspace_api_keys(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Return the single API-keys row for this workspace, or null if not set yet."""
    row = await WorkspaceApiKeysService(session).get(workspace_id)
    return to_read(row) if row is not None else None


@router.put("", response_model=WorkspaceApiKeysRead)
async def upsert_workspace_api_keys(
    workspace_id: uuid.UUID,
    payload: WorkspaceApiKeysUpsert,
    _membership=Depends(require_workspace_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """Create the row on first save, update in place afterward — always one record."""
    service = WorkspaceApiKeysService(session)
    row = await service.upsert(workspace_id, payload)
    await session.commit()
    await session.refresh(row)
    return to_read(row)
