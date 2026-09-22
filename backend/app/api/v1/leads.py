import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db_session,
    require_workspace_editor,
    require_workspace_member,
)
from app.core.config import Settings, get_settings
from app.models.contact import LeadStatus
from app.repositories.ai_generation_repository import AIGenerationRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.ai_generation import AIGenerationRead
from app.schemas.contact import (
    BulkStatusUpdate,
    BulkStatusUpdateResponse,
    BulkTagRequest,
    BulkTagResponse,
    ContactRead,
    LeadStatusUpdate,
    RevealResponse,
)
from app.schemas.csv_import import ImportMapping, ImportPreviewResponse, ImportResultResponse
from app.schemas.lead_qualification import LeadQualificationRead
from app.schemas.note import NoteCreate, NoteRead
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.csv_export_service import CsvExportService
from app.services.csv_import_service import CsvImportService, preview_csv
from app.services.lead_qualification_service import LeadQualificationService
from app.services.lead_reveal_service import LeadRevealService
from app.services.personalization_service import PersonalizationService

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=list[ContactRead])
async def list_leads(
    workspace_id: uuid.UUID,
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    tag_id: uuid.UUID | None = Query(default=None),
    company_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ContactRepository(session)
    return await repo.search(
        workspace_id,
        status=status_filter,
        tag_id=tag_id,
        company_id=company_id,
        text=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


@router.patch("/bulk-status", response_model=BulkStatusUpdateResponse)
async def bulk_update_lead_status(
    workspace_id: uuid.UUID,
    payload: BulkStatusUpdate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ContactRepository(session)
    updated = not_found = 0
    for contact_id in payload.contact_ids:
        contact = await repo.get_by_id(workspace_id, contact_id)
        if contact is None:
            not_found += 1
            continue
        contact.status = payload.status
        updated += 1
    await session.commit()
    return BulkStatusUpdateResponse(updated=updated, not_found=not_found)


@router.post("/bulk-tag", response_model=BulkTagResponse)
async def bulk_tag_leads(
    workspace_id: uuid.UUID,
    payload: BulkTagRequest,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    contact_repo = ContactRepository(session)
    tag_repo = TagRepository(session)

    tag = await tag_repo.get_by_id(workspace_id, payload.tag_id)
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")

    tagged = already_tagged = not_found = 0
    for contact_id in payload.contact_ids:
        contact = await contact_repo.get_by_id(workspace_id, contact_id)
        if contact is None:
            not_found += 1
            continue
        if await tag_repo.is_tagged(contact_id, payload.tag_id):
            already_tagged += 1
            continue
        tag_repo.tag_contact(contact_id=contact_id, tag_id=payload.tag_id)
        tagged += 1
    await session.commit()
    return BulkTagResponse(tagged=tagged, already_tagged=already_tagged, not_found=not_found)


@router.get("/export")
async def export_leads(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    csv_content = await CsvExportService(session).export(workspace_id=workspace_id)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_lead_import(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    _membership=Depends(require_workspace_member),
):
    content = await file.read()
    try:
        return preview_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/import", response_model=ImportResultResponse)
async def import_leads(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    content = await file.read()
    try:
        mapping = ImportMapping(mapping=json.loads(mapping_json))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="mapping_json must be valid JSON"
        ) from exc

    try:
        return await CsvImportService(session).execute(
            workspace_id=workspace_id, content=content, mapping=mapping
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{contact_id}", response_model=ContactRead)
async def get_lead(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ContactRepository(session)
    contact = await repo.get_by_id(workspace_id, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return contact


@router.post("/{contact_id}/reveal", response_model=RevealResponse)
async def reveal_lead_details(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Spends a provider credit (e.g. an Apollo credit) to reveal a masked
    search result's real email/phone/name — an explicit, per-lead action,
    not something that happens automatically for every search result."""
    service = LeadRevealService(session, settings)
    contact, revealed = await service.reveal(workspace_id=workspace_id, contact_id=contact_id)
    return RevealResponse(contact=contact, revealed=revealed)


@router.post("/{contact_id}/qualify", response_model=LeadQualificationRead)
async def qualify_lead(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Scores this lead against the need/capacity/timing/reachability
    rubric via an AI provider — an explicit, on-demand action per lead,
    not something that runs automatically for every search result."""
    service = LeadQualificationService(session, settings)
    return await service.qualify(workspace_id=workspace_id, contact_id=contact_id)


@router.post("/{contact_id}/personalize", response_model=AIGenerationRead)
async def personalize_lead_outreach(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    service = PersonalizationService(session, settings)
    return await service.personalize(workspace_id=workspace_id, contact_id=contact_id)


@router.get("/{contact_id}/personalizations", response_model=list[AIGenerationRead])
async def list_lead_personalizations(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    return await AIGenerationRepository(session).list_for_contact(workspace_id, contact_id)


async def _get_contact_or_404(session, workspace_id, contact_id):
    contact = await ContactRepository(session).get_by_id(workspace_id, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return contact


@router.patch("/{contact_id}/status", response_model=ContactRead)
async def update_lead_status(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: LeadStatusUpdate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    contact = await _get_contact_or_404(session, workspace_id, contact_id)
    contact.status = payload.status
    await session.commit()
    await session.refresh(contact)
    return contact


@router.post("/{contact_id}/notes", response_model=NoteRead, status_code=201)
async def create_lead_note(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: NoteCreate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_contact_or_404(session, workspace_id, contact_id)
    note = NoteRepository(session).create(
        workspace_id=workspace_id, contact_id=contact_id, author_user_id=current_user.id,
        text=payload.text,
    )
    await session.commit()
    await session.refresh(note)
    return note


@router.get("/{contact_id}/notes", response_model=list[NoteRead])
async def list_lead_notes(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_contact_or_404(session, workspace_id, contact_id)
    return await NoteRepository(session).list_for_contact(workspace_id, contact_id)


@router.post("/{contact_id}/tasks", response_model=TaskRead, status_code=201)
async def create_lead_task(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: TaskCreate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_contact_or_404(session, workspace_id, contact_id)
    task = TaskRepository(session).create(
        workspace_id=workspace_id, contact_id=contact_id, **payload.model_dump()
    )
    await session.commit()
    await session.refresh(task)
    return task


@router.get("/{contact_id}/tasks", response_model=list[TaskRead])
async def list_lead_tasks(
    contact_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_contact_or_404(session, workspace_id, contact_id)
    return await TaskRepository(session).list_for_contact(workspace_id, contact_id)


@router.patch("/{contact_id}/tasks/{task_id}", response_model=TaskRead)
async def update_lead_task(
    contact_id: uuid.UUID,
    task_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: TaskUpdate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_contact_or_404(session, workspace_id, contact_id)
    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(workspace_id, task_id)
    if task is None or task.contact_id != contact_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field_name, value)

    await session.commit()
    await session.refresh(task)
    return task
