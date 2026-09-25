from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values


class RecipientStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    SUPPRESSED = "suppressed"
    COMPLETED = "completed"
    FAILED = "failed"


class CampaignRecipient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One contact's enrollment in one campaign. `current_step_number`
    tracks progress through CampaignStep sequence; `next_send_at` is when
    the next step is due — the sending service only ever touches rows
    where this has passed and status is PENDING."""

    __tablename__ = "campaign_recipients"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus, name="recipient_status", values_callable=str_enum_values), default=RecipientStatus.PENDING, nullable=False
    )
    current_step_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_send_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contact: Mapped["Contact"] = relationship(back_populates="campaign_recipients")  # noqa: F821
