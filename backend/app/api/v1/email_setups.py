import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_editor, require_workspace_member
from app.repositories.email_setup_repository import EmailSetupRepository
from app.schemas.email_setup import (
    EmailSetupCreate,
    EmailSetupDefaults,
    EmailSetupImportResult,
    EmailSetupRead,
    EmailSetupUpdate,
)
from app.services.email_setup_service import EmailSetupService, get_defaults, to_read

router = APIRouter(prefix="/email-setups", tags=["email-setup"])


@router.get("/defaults", response_model=EmailSetupDefaults)
async def email_setup_defaults(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
):
    """Placeholder defaults for the create form (mirrors .env SMTP_* keys)."""
    return get_defaults()


@router.get("", response_model=list[EmailSetupRead])
async def list_email_setups(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    setups = await EmailSetupRepository(session).list_for_workspace(workspace_id)
    return [to_read(s) for s in setups]


@router.post("", response_model=EmailSetupRead, status_code=201)
async def create_email_setup(
    workspace_id: uuid.UUID,
    payload: EmailSetupCreate,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = EmailSetupService(session)
    setup = await service.create(workspace_id, payload)
    await session.commit()
    await session.refresh(setup)
    return to_read(setup)


@router.post("/import", response_model=EmailSetupImportResult)
async def import_email_setups(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload a .csv file")

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV file is empty")

    service = EmailSetupService(session)
    try:
        result = await service.import_csv(workspace_id, content)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await session.commit()
    return result


@router.get("/{email_setup_id}", response_model=EmailSetupRead)
async def get_email_setup(
    email_setup_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    setup = await EmailSetupRepository(session).get_by_id(workspace_id, email_setup_id)
    if setup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
    return to_read(setup)


@router.patch("/{email_setup_id}", response_model=EmailSetupRead)
async def update_email_setup(
    email_setup_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: EmailSetupUpdate,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = EmailSetupService(session)
    setup = await service.update(workspace_id, email_setup_id, payload)
    if setup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
    await session.commit()
    await session.refresh(setup)
    return to_read(setup)


@router.delete("/{email_setup_id}", status_code=204)
async def delete_email_setup(
    email_setup_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    deleted = await EmailSetupService(session).delete(workspace_id, email_setup_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
    await session.commit()
