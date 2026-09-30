import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.models.contact import LeadStatus
from app.schemas.lead_qualification import LeadQualificationSummary


class ContactSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    external_id: str | None
    source_url: str | None
    source_type: str
    retrieved_at: datetime


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID | None
    company_name: str | None
    company_phone: str | None
    first_name: str | None
    last_name: str | None
    full_name: str | None
    job_title: str | None
    department: str | None
    seniority: str | None
    email: str | None
    email_status: str | None
    #: True once a reveal request for this contact's email has been made
    #: (auto-triggered right after search, now in the background — see
    #: reveal_contacts_in_background), regardless of whether it found one.
    #: Same "still waiting" vs "never asked" purpose as
    #: phone_reveal_attempted below.
    email_reveal_attempted: bool
    phone: str | None
    #: True once a phone-reveal request has been sent to Apollo for this
    #: contact, regardless of whether a number ever came back — lets the
    #: UI tell "still waiting on Apollo's webhook" apart from "never
    #: asked" without guessing from `phone` alone.
    phone_reveal_attempted: bool
    linkedin_url: str | None
    city: str | None
    state: str | None
    country: str | None
    industry: str | None
    sub_industry: str | None
    company_headcount: str | None
    company_revenue: str | None
    status: LeadStatus
    field_provenance: dict[str, Any]
    revealable: bool
    latest_qualification: LeadQualificationSummary | None
    #: WhatsApp-style read-receipt signal — "sent" (one tick), "opened"
    #: (two ticks), or None if no campaign has ever emailed this lead.
    email_track_status: Literal["sent", "opened"] | None
    first_seen: datetime
    last_seen: datetime


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class BulkStatusUpdate(BaseModel):
    contact_ids: list[uuid.UUID]
    status: LeadStatus


class BulkStatusUpdateResponse(BaseModel):
    updated: int
    not_found: int


class BulkTagRequest(BaseModel):
    contact_ids: list[uuid.UUID]
    tag_id: uuid.UUID


class BulkTagResponse(BaseModel):
    tagged: int
    already_tagged: int
    not_found: int


class RevealResponse(BaseModel):
    contact: ContactRead
    revealed: bool
