from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values
from app.providers.base import ProviderCategory


class SearchBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per search run from the Discover page — groups the
    companies/contacts that run touched so leads can be reviewed by the
    batch that found them, not just as one flat list. `sequence` is a
    per-workspace, human-facing counter ("Batch 01", "Batch 02", ...).

    Manual Create-batch rows use the same table/shape as Discover; the
    optional display name lives in criteria_snapshot["name"] so no extra
    columns are required on existing production DBs.
    """

    __tablename__ = "search_batches"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[ProviderCategory] = mapped_column(
        Enum(ProviderCategory, name="provider_category", values_callable=str_enum_values), nullable=False
    )
    criteria_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    companies_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    companies_matched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contacts_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contacts_matched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: SMTP mailbox used for auto draft→send after this batch is built.
    email_setup_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("email_setups.id", ondelete="SET NULL"), nullable=True
    )
    #: Campaign created/used for the auto-send of this batch.
    outreach_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    #: idle | drafting | sending | completed | failed | skipped
    outreach_status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)

    #: Set whenever a scoring/reveal/phone-enrich sweep is scheduled for
    #: this batch (auto right after search, or a manual "all" click) —
    #: lets the API report whether that sweep is genuinely still running
    #: (timestamp set AND work still outstanding), independent of any
    #: frontend tab being open. Never reset back to None on completion —
    #: "still outstanding" is recomputed from current contact state each
    #: time, so a finished sweep naturally reads as inactive regardless of
    #: when it was requested.
    qualify_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reveal_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Phone enrichment is bounded (see PhoneEnrichmentService/batch page
    #: docstrings — Apollo's "no number found" is a permanent miss with no
    #: explicit signal), so this timestamp also caps how long "active" is
    #: reported, not just whether a sweep ever ran.
    phone_enrich_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    links: Mapped[list["SearchBatchContact"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class SearchBatchContact(Base):
    """Join row: which contacts a given SearchBatch touched, and whether
    this particular batch is what created the contact (vs. re-matched an
    already-existing one)."""

    __tablename__ = "search_batch_contacts"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_batches.id", ondelete="CASCADE"), primary_key=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True
    )
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    batch: Mapped["SearchBatch"] = relationship(back_populates="links")
