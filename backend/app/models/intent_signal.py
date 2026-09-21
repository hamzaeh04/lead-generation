from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values


class IntentSignalType(StrEnum):
    RECENT_POST = "recent_post"
    SERVICE_REQUEST = "service_request"
    FUNDING = "funding"
    FUNDING_ANNOUNCEMENT = "funding_announcement"
    HIRING = "hiring"
    NEW_JOB_POST = "new_job_post"
    JOB_CHANGE = "job_change"
    NEW_COMPANY = "new_company"
    NEW_LOCATION = "new_location"
    EXPANSION = "expansion"
    NEGATIVE_REVIEW = "negative_review"
    PRODUCT_LAUNCH = "product_launch"
    TECHNOLOGY_CHANGE = "technology_change"
    COMPETITOR_MENTION = "competitor_mention"
    ASKING_FOR_RECOMMENDATION = "asking_for_recommendation"
    ENGAGEMENT_WITH_RELEVANT_CONTENT = "engagement_with_relevant_content"
    EVENT_ATTENDANCE = "event_attendance"
    COMPANY_GROWTH = "company_growth"
    OTHER = "other"


class IntentSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single buying-intent observation about a company. Every row must
    trace back to a real source (source_url) — there is no path to create
    one without it, matching the platform's never-fabricate-intent rule."""

    __tablename__ = "intent_signals"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[IntentSignalType] = mapped_column(
        Enum(IntentSignalType, name="intent_signal_type", values_callable=str_enum_values), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    signal_text: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
