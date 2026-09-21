import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_editor, require_workspace_member
from app.core.config import Settings, get_settings
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.icp_profile_repository import ICPProfileRepository
from app.repositories.intent_signal_repository import IntentSignalRepository
from app.schemas.company import (
    CompanyRead,
    CompanySourceRead,
    DecisionMakerSearchRequest,
    DecisionMakerSearchResponse,
)
from app.schemas.icp_profile import ICPScoreRead
from app.schemas.intent_signal import IntentScoreRead, IntentSignalCreate, IntentSignalRead
from app.services.decision_maker_service import DecisionMakerService
from app.services.icp_score_service import compute_icp_score
from app.services.intent_score_service import compute_intent_score

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyRead])
async def list_companies(
    workspace_id: uuid.UUID,
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CompanyRepository(session)
    return await repo.list_for_workspace(workspace_id, search=search, limit=limit, offset=offset)


@router.get("/{company_id}/sources", response_model=list[CompanySourceRead])
async def list_company_sources(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_company_or_404(session, workspace_id, company_id)
    return await CompanyRepository(session).list_sources(workspace_id, company_id)


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = CompanyRepository(session)
    company = await repo.get_by_id(workspace_id, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def _get_company_or_404(session, workspace_id, company_id):
    company = await CompanyRepository(session).get_by_id(workspace_id, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.post(
    "/{company_id}/intent-signals", response_model=IntentSignalRead, status_code=201
)
async def create_intent_signal(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: IntentSignalCreate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_company_or_404(session, workspace_id, company_id)

    repo = IntentSignalRepository(session)
    signal = repo.create(
        workspace_id=workspace_id,
        company_id=company_id,
        signal_type=payload.signal_type,
        provider="manual",
        source=payload.source,
        source_url=payload.source_url,
        signal_text=payload.signal_text,
        confidence=payload.confidence,
        detected_at=payload.detected_at or datetime.now(timezone.utc),
    )
    await session.commit()
    await session.refresh(signal)
    return signal


@router.get("/{company_id}/intent-signals", response_model=list[IntentSignalRead])
async def list_intent_signals(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_company_or_404(session, workspace_id, company_id)
    return await IntentSignalRepository(session).list_for_company(workspace_id, company_id)


@router.get("/{company_id}/intent-score", response_model=IntentScoreRead)
async def get_intent_score(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_company_or_404(session, workspace_id, company_id)
    signals = await IntentSignalRepository(session).list_for_company(workspace_id, company_id)
    return IntentScoreRead(
        company_id=company_id,
        score=compute_intent_score(signals),
        signal_count=len(signals),
        signals=signals,
    )


@router.get("/{company_id}/icp-score", response_model=ICPScoreRead)
async def get_icp_score(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    icp_profile_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    company = await _get_company_or_404(session, workspace_id, company_id)

    icp = await ICPProfileRepository(session).get_by_id(workspace_id, icp_profile_id)
    if icp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ICP profile not found")

    contacts = await ContactRepository(session).list_for_company(workspace_id, company_id)
    score, matched_criteria = compute_icp_score(company, contacts, icp)

    return ICPScoreRead(
        company_id=company_id,
        icp_profile_id=icp_profile_id,
        score=score,
        matched_criteria=matched_criteria,
    )


@router.post("/{company_id}/decision-makers", response_model=DecisionMakerSearchResponse)
async def find_company_decision_makers(
    company_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: DecisionMakerSearchRequest,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Finds real people at this company filtered by job title — owner,
    founder, CEO, etc. by default — via the highest-priority enabled
    person_discovery provider (currently Apollo), waterfalling to the next
    on failure. Never guesses a name/email: an empty result is a normal
    outcome, not an error, when nothing is found."""
    service = DecisionMakerService(session, settings)
    result = await service.find_decision_makers(
        workspace_id=workspace_id, company_id=company_id, target_titles=payload.target_titles
    )
    return DecisionMakerSearchResponse(**result)
