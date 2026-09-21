from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import User
from app.providers.base import DiscoveryCriteria
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.search import (
    DiscoveryCriteriaSchema,
    ParsePromptRequest,
    ParsePromptResponse,
    SearchExecuteRequest,
    SearchExecuteResponse,
)
from app.services.prospect_prompt_service import ProspectPromptService
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])

# DiscoveryCriteriaSchema fields the AI prompt parser may fill in directly;
# anything else it returns is provider-specific and lands in extra_filters
# instead (e.g. Apollo's "technologies", Smartlead's "department").
_CRITERIA_TOP_LEVEL_FIELDS = {
    "keywords",
    "industry",
    "country",
    "state",
    "city",
    "company_name",
    "domain",
    "employee_count_min",
    "employee_count_max",
    "job_titles",
    "seniorities",
}


@router.post("/execute", response_model=SearchExecuteResponse)
async def execute_search(
    payload: SearchExecuteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    membership = await WorkspaceRepository(session).get_membership(
        workspace_id=payload.workspace_id, user_id=current_user.id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace"
        )

    criteria = DiscoveryCriteria(**payload.criteria.model_dump())
    service = SearchService(session, settings)
    result = await service.execute(
        workspace_id=payload.workspace_id,
        provider_name=payload.provider,
        category=payload.category,
        criteria=criteria,
        created_by=current_user.id,
    )

    return SearchExecuteResponse(
        provider=payload.provider,
        category=payload.category,
        **result,
    )


@router.post("/parse-prompt", response_model=ParsePromptResponse)
async def parse_prompt(
    payload: ParsePromptRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Translates a natural-language prospecting sentence into structured
    search criteria for the given provider — never runs a search itself.
    The caller (Discover page) shows the parsed criteria for review/editing
    before actually calling /execute, so a bad AI parse is always visible
    and correctable rather than silently driving a search."""
    membership = await WorkspaceRepository(session).get_membership(
        workspace_id=payload.workspace_id, user_id=current_user.id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace"
        )

    service = ProspectPromptService(session, settings)
    parsed = await service.parse(
        prompt=payload.prompt, target_provider=payload.provider, workspace_id=payload.workspace_id
    )

    top_level = {k: v for k, v in parsed.items() if k in _CRITERIA_TOP_LEVEL_FIELDS}
    extra_filters = {k: v for k, v in parsed.items() if k not in _CRITERIA_TOP_LEVEL_FIELDS}
    try:
        criteria = DiscoveryCriteriaSchema(**top_level, extra_filters=extra_filters)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned an unusable filter structure: {exc}",
        ) from exc
    return ParsePromptResponse(criteria=criteria)
