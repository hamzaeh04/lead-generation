from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, Uuid, func, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values
from app.models.campaign_recipient import RecipientStatus

_EMAIL_OPENED_OR_BEYOND = {RecipientStatus.OPENED, RecipientStatus.CLICKED, RecipientStatus.REPLIED}
_EMAIL_SENT_OR_BEYOND = _EMAIL_OPENED_OR_BEYOND | {
    RecipientStatus.SENT,
    RecipientStatus.BOUNCED,
    RecipientStatus.UNSUBSCRIBED,
    RecipientStatus.COMPLETED,
}


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
    #: True once a phone-reveal request has been sent to Apollo for this
    #: contact (see PhoneEnrichmentService), regardless of whether Apollo's
    #: webhook eventually delivers a number — same never-re-request
    #: convention as email_reveal_attempted, for the same reason (no
    #: server-side "already tried" memory on Apollo's side).
    phone_reveal_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    qualifications: Mapped[list["LeadQualification"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
    campaign_recipients: Mapped[list["CampaignRecipient"]] = relationship(  # noqa: F821
        back_populates="contact"
    )

    @property
    def email_track_status(self) -> Literal["sent", "opened"] | None:
        """WhatsApp-style read-receipt signal for the leads/batch table:
        "opened" (double tick) once any campaign enrollment has actually
        been opened, "sent" (single tick) once any has gone out, None
        until then (never show a tick for a lead that was never emailed).
        Deliberately reads CampaignRecipient.status rather than
        Contact.status — the latter is a CRM pipeline stage the user can
        move by hand (e.g. to "won"), which would otherwise make the tick
        disappear even though the email genuinely was opened. Same
        unloaded-relationship guard as company_name — with a CRM-status
        fallback when recipients weren't eager-loaded so the Delivery
        column still works on lighter payloads."""
        if "campaign_recipients" not in inspect(self).unloaded and self.campaign_recipients:
            statuses = {r.status for r in self.campaign_recipients}
            if statuses & _EMAIL_OPENED_OR_BEYOND:
                return "opened"
            if statuses & _EMAIL_SENT_OR_BEYOND:
                return "sent"

        # Fallback when relationship wasn't loaded (or is empty after a
        # stale cache): use CRM pipeline stages set by the send/open path.
        if self.status in {
            LeadStatus.OPENED,
            LeadStatus.CLICKED,
            LeadStatus.REPLIED,
            LeadStatus.INTERESTED,
            LeadStatus.MEETING,
            LeadStatus.WON,
        }:
            return "opened"
        if self.status == LeadStatus.CONTACTED:
            return "sent"
        return None

    @property
    def latest_qualification(self) -> "LeadQualification | None":  # noqa: F821
        """Most recent scoring run, or None if never scored. Same
        unloaded-relationship guard as company_name — fails safe (None)
        rather than crashing when `qualifications` isn't eager-loaded."""
        if "qualifications" in inspect(self).unloaded:
            return None
        if not self.qualifications:
            return None
        return max(self.qualifications, key=lambda q: q.scored_at)

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
        a source supports it (Apollo always; Smartlead only if its source
        has the `filter_id` its unlock call needs — captured at search
        time, so a contact found before that existed can't be unlocked),
        there's no email yet, and reveal hasn't already been tried once
        and come up empty. That last check matters because neither
        provider's unlock call has "already tried" memory of its own —
        calling it again for the same person spends another credit for
        the same non-result, so the UI must stop offering the button once
        one attempt has failed rather than let it be clicked repeatedly.
        Same unloaded-relationship guard as company_name — fails safe
        (False) when `sources` isn't eager-loaded, not a crash."""
        if self.email or self.email_reveal_attempted:
            return False
        if "sources" in inspect(self).unloaded:
            return False
        for source in self.sources:
            if source.provider == "apollo":
                return True
            if source.provider == "smartlead" and (source.raw_reference or {}).get("_smartlead_filter_id"):
                return True
        return False


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
