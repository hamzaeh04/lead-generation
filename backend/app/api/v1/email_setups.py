import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
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
async def email_setup_defaults(_current_user=Depends(get_current_user)):
    """Placeholder defaults for the create form (mirrors .env SMTP_* keys)."""
    return get_defaults()


@router.get("", response_model=list[EmailSetupRead])
async def list_email_setups(
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    setups = await EmailSetupRepository(session).list_all()
    return [to_read(s) for s in setups]


@router.post("", response_model=EmailSetupRead, status_code=201)
async def create_email_setup(
    payload: EmailSetupCreate,
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = EmailSetupService(session)
    try:
        setup = await service.create(payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(setup)
    return to_read(setup)


@router.post("/import", response_model=EmailSetupImportResult)
async def import_email_setups(
    file: UploadFile = File(...),
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload a .csv file")

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV file is empty")

    service = EmailSetupService(session)
    try:
        result = await service.import_csv(content)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await session.commit()
    return result


@router.get("/{email_setup_id}", response_model=EmailSetupRead)
async def get_email_setup(
    email_setup_id: uuid.UUID,
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    setup = await EmailSetupRepository(session).get_by_id(email_setup_id)
    if setup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
    return to_read(setup)


@router.patch("/{email_setup_id}", response_model=EmailSetupRead)
async def update_email_setup(
    email_setup_id: uuid.UUID,
    payload: EmailSetupUpdate,
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = EmailSetupService(session)
    try:
        setup = await service.update(email_setup_id, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if setup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
    await session.commit()
    await session.refresh(setup)
    return to_read(setup)


@router.delete("/{email_setup_id}", status_code=204)
async def delete_email_setup(
    email_setup_id: uuid.UUID,
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    deleted = await EmailSetupService(session).delete(email_setup_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email setup not found")
    await session.commit()
