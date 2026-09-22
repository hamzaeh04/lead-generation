from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LeadQualification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One AI-scored qualification run against the lead-qualification
    rubric (need/capacity/timing/reachability, tiers A-E, override/
    disqualifier rules). A contact can be re-scored over time — this is
    an append-only log, not a single mutable field, so `Contact.
    latest_qualification` picks the most recent row rather than this
    table ever being updated in place. Mirrors AIGeneration's pattern:
    provider/model/prompt_version for auditability, raw_response kept
    for debugging a bad parse."""

    __tablename__ = "lead_qualifications"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    score_version: Mapped[str] = mapped_column(String(50), nullable=False)

    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(1), nullable=False)
    tier_rationale: Mapped[str] = mapped_column(Text, nullable=False)

    # {"need": {"score": 0, "confidence": 0, "reasoning": "..."}, "capacity": {...}, ...}
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # [{"dimension": ..., "claim": ..., "observation": ..., "source_platform": ..., ...}]
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    overrides_triggered: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    disqualifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # [{"field": ..., "why_it_matters": ..., "how_to_obtain": ...}]
    missing_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    enrichment_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recommended_channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recommended_angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    objection_to_expect: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_deal_band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    uncertainty_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contact: Mapped["Contact"] = relationship(back_populates="qualifications")  # noqa: F821
