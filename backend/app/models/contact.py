from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, Uuid, func, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values


class LeadStatus(StrEnum):
    """CRM pipeline stage (section 47). Distinct from CampaignRecipient's
    per-enrollment status — this is the durable, contact-level stage that
    persists across (and outside of) any single campaign."""

    NEW = "new"
    VERIFIED = "verified"
    READY_FOR_OUTREACH = "ready_for_outreach"
    CONTACTED = "contacted"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    INTERESTED = "interested"
    MEETING = "meeting"
    WON = "won"
    LOST = "lost"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical person/lead entity. A person's name is never invented —
    every Contact must trace back to at least one ContactSource."""

    __tablename__ = "contacts"
    __table_args__ = (
        Index("ix_contacts_workspace_email", "workspace_id", "email"),
        Index("ix_contacts_workspace_company", "workspace_id", "company_id"),
        Index("ix_contacts_workspace_status", "workspace_id", "status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )

    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    #: Deliverability status from a provider's enrichment (e.g. Apollo
    #: reveal returns "verified"/"unverified"/etc.) — real data from the
    #: provider, never inferred or guessed by us.
    email_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: True once a /reveal call has been made for this contact, regardless
    #: of whether it actually found an email. Apollo's /people/match has
    #: no server-side memory of "already tried" — calling it again for the
    #: same person spends another credit for the identical result. Once
    #: one attempt comes back with no email, we stop offering "Reveal"
    #: rather than let it be clicked repeatedly for nothing.
    email_reveal_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: This person's own location — distinct from the company's address
    #: (e.g. a remote employee). Currently only populated by Smartlead's
    #: SmartProspect search, which reports it per-person.
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Firmographic fields reported by the provider alongside this specific
    #: person (not read from the Company record — a provider may know this
    #: about the company at search time without us having enriched Company
    #: with it separately). Bands (e.g. "$1 - 10M") are stored as-is rather
    #: than parsed into a single number, since that would fabricate false
    #: precision the provider never gave us.
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sub_industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_headcount: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_revenue: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", values_callable=str_enum_values), default=LeadStatus.NEW, nullable=False
    )

    field_provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped["Company | None"] = relationship(back_populates="contacts")
    sources: Mapped[list["ContactSource"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )

    @property
    def company_name(self) -> str | None:
        """Read by ContactRead for list/detail display. Guards against
        triggering a lazy load: in async SQLAlchemy, touching an unloaded
        relationship outside a greenlet context raises MissingGreenlet.
        Callers that want this populated must eager-load `company` (see
        ContactRepository) — this just fails safe (None) rather than
        crashing when they don't."""
        if "company" in inspect(self).unloaded:
            return None
        return self.company.name if self.company else None

    @property
    def company_phone(self) -> str | None:
        """The company's general phone line — a fallback the UI shows when
        no personal number was found for this specific contact, since for a
        small business that's often the only way to reach anyone there.
        Same unloaded-relationship guard as company_name."""
        if "company" in inspect(self).unloaded:
            return None
        return self.company.phone if self.company else None

    @property
    def revealable(self) -> bool:
        """True only when clicking "Reveal" could plausibly do something:
        a source supports it (currently just Apollo — Smartlead's masked
        SmartProspect results have no API-based unlock, only a dashboard
        one), there's no email yet, and reveal hasn't already been tried
        once and come up empty. That last check matters because Apollo's
        /people/match has no "already tried" memory of its own — calling
        it again for the same person spends another credit for the same
        non-result, so the UI must stop offering the button once one
        attempt has failed rather than let it be clicked repeatedly.
        Same unloaded-relationship guard as company_name — fails safe
        (False) when `sources` isn't eager-loaded, not a crash."""
        if self.email or self.email_reveal_attempted:
            return False
        if "sources" in inspect(self).unloaded:
            return False
        return any(source.provider == "apollo" for source in self.sources)


class ContactSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contact_sources"
    __table_args__ = (Index("ix_contact_sources_contact_id", "contact_id"),)

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    raw_reference: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contact: Mapped["Contact"] = relationship(back_populates="sources")
