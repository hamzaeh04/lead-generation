from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import User
from app.providers.base import DiscoveryCriteria
from app.repositories.search_batch_repository import SearchBatchRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.search import (
    DiscoveryCriteriaSchema,
    ParsePromptRequest,
    ParsePromptResponse,
    SearchExecuteRequest,
    SearchExecuteResponse,
)
from app.services.batch_outreach_service import draft_batch_in_background
from app.services.lead_reveal_service import _AUTO_REVEAL_PROVIDERS
from app.services.prospect_prompt_service import ProspectPromptService
from app.services.search_service import (
    SearchService,
    qualify_contacts_in_background,
    reveal_contacts_in_background,
)

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

# DiscoveryCriteriaSchema's str fields vs. its list[str] fields — the model
# is told which shape each one is, but LLMs still sometimes cross the
# streams (e.g. "restaurant owners" -> keywords: ["restaurants"] instead
# of "restaurants"). A ValidationError here is a dead end for the user
# (the whole point of the AI-prompt flow is not making them hand-build
# filters), so the obvious shape mismatch is coerced instead of rejected —
# this never invents a *value*, only reshapes one the model already gave.
_CRITERIA_STRING_FIELDS = {"keywords", "industry", "country", "state", "city", "company_name", "domain"}
_CRITERIA_LIST_FIELDS = {"job_titles", "seniorities"}


def _normalize_criteria_types(top_level: dict) -> dict:
    normalized = dict(top_level)
    for field in _CRITERIA_STRING_FIELDS:
        value = normalized.get(field)
        if isinstance(value, list):
            joined = ", ".join(str(v) for v in value if v not in (None, ""))
            if joined:
                normalized[field] = joined
            else:
                del normalized[field]
    for field in _CRITERIA_LIST_FIELDS:
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = [value]
    return normalized


@router.post("/execute", response_model=SearchExecuteResponse)
async def execute_search(
    payload: SearchExecuteRequest,
    background_tasks: BackgroundTasks,
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

    # Reveal + score + draft all run after the response is sent so a large
    # batch never risks the HTTP request timing out. Reveal is scheduled
    # first (same order the old inline code ran in) so qualification still
    # sees real email/location/seniority data once it runs, rather than
    # the pre-reveal masked state — BackgroundTasks run in the order
    # they're added. Drafts are scheduled separately from scoring so they
    # start immediately — they used to wait until every lead finished
    # qualify (often many minutes), which made it look like drafts only
    # existed after clicking "Generate draft".
    contact_ids = [contact.id for contact in result["contacts"]]
    batch_id = result.get("batch_id")
    batch = await SearchBatchRepository(session).get_by_id(payload.workspace_id, batch_id) if batch_id else None
    now = datetime.now(timezone.utc)
    if contact_ids and payload.provider in _AUTO_REVEAL_PROVIDERS:
        background_tasks.add_task(
            reveal_contacts_in_background,
            workspace_id=payload.workspace_id,
            contact_ids=contact_ids,
            provider=payload.provider,
            settings=settings,
        )
        if batch is not None:
            batch.reveal_requested_at = now
    if contact_ids:
        background_tasks.add_task(
            qualify_contacts_in_background,
            workspace_id=payload.workspace_id,
            contact_ids=contact_ids,
            settings=settings,
        )
        if batch is not None:
            batch.qualify_requested_at = now
    if batch is not None:
        await session.commit()
    if batch_id is not None:
        background_tasks.add_task(
            draft_batch_in_background,
            workspace_id=payload.workspace_id,
            batch_id=batch_id,
            settings=settings,
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

    top_level = _normalize_criteria_types(
        {k: v for k, v in parsed.items() if k in _CRITERIA_TOP_LEVEL_FIELDS}
    )
    extra_filters = {k: v for k, v in parsed.items() if k not in _CRITERIA_TOP_LEVEL_FIELDS}
    try:
        criteria = DiscoveryCriteriaSchema(**top_level, extra_filters=extra_filters)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned an unusable filter structure: {exc}",
        ) from exc
    return ParsePromptResponse(criteria=criteria)
