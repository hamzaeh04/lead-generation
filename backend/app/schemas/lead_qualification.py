import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LeadQualificationSummary(BaseModel):
    """Lightweight — for embedding in ContactRead so a lead table can show
    a Grade/Score column without a separate request per row."""

    model_config = ConfigDict(from_attributes=True)

    tier: str
    composite_score: float
    confidence: int
    scored_at: datetime


class LeadQualificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    provider: str
    model: str
    prompt_version: str
    score_version: str
    composite_score: float
    confidence: int
    tier: str
    tier_rationale: str
    dimensions: dict[str, Any]
    evidence: list[dict[str, Any]]
    overrides_triggered: list[str]
    disqualifier: str | None
    missing_data: list[dict[str, Any]]
    enrichment_priority: str | None
    recommended_channel: str | None
    recommended_angle: str | None
    objection_to_expect: str | None
    estimated_deal_band: str | None
    next_review_date: date | None
    human_review_required: bool
    human_review_reason: str | None
    uncertainty_notes: str | None
    scored_at: datetime
