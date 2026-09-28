from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status", values_callable=str_enum_values), default=CampaignStatus.DRAFT, nullable=False
    )
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_email: Mapped[str] = mapped_column(String(320), nullable=False)
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    daily_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=False)
    #: Minutes between consecutive first-touch sends (5/10/15/30/45/60). Null = blast.
    send_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Local HH:MM window start/end in `timezone` (inclusive start, exclusive end).
    send_window_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    send_window_end: Mapped[str | None] = mapped_column(String(5), nullable=True)

    steps: Mapped[list["CampaignStep"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignStep.step_number"
    )


class CampaignStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_steps"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="steps")
