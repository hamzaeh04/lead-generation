import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.campaign import CampaignStatus

_ALLOWED_SEND_INTERVALS = {5, 10, 15, 30, 45, 60}


class CampaignStepCreate(BaseModel):
    step_number: int = Field(ge=1)
    delay_days: int = Field(default=0, ge=0)
    subject: str
    body: str
    active: bool = True


class CampaignStepUpdate(BaseModel):
    step_number: int | None = Field(default=None, ge=1)
    delay_days: int | None = Field(default=None, ge=0)
    subject: str | None = None
    body: str | None = None
    active: bool | None = None


class CampaignStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step_number: int
    delay_days: int
    subject: str
    body: str
    active: bool


class CampaignCreate(BaseModel):
    name: str
    from_name: str | None = None
    from_email: str
    reply_to: str | None = None
    daily_limit: int = Field(default=50, ge=1)
    timezone: str = "UTC"
    send_interval_minutes: int | None = Field(default=None, ge=5, le=60)
    send_window_start: str | None = Field(default=None, max_length=5)
    send_window_end: str | None = Field(default=None, max_length=5)

    @field_validator("send_interval_minutes")
    @classmethod
    def validate_interval(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v not in _ALLOWED_SEND_INTERVALS:
            raise ValueError("send_interval_minutes must be one of 5, 10, 15, 30, 45, 60")
        return v


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: CampaignStatus
    from_name: str | None
    from_email: str
    reply_to: str | None
    daily_limit: int
    timezone: str
    send_interval_minutes: int | None = None
    send_window_start: str | None = None
    send_window_end: str | None = None
    steps: list[CampaignStepRead] = []


class EnrollRequest(BaseModel):
    contact_ids: list[uuid.UUID] = Field(default_factory=list)
    batch_ids: list[uuid.UUID] = Field(default_factory=list)
    email_setup_id: uuid.UUID | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1)
    #: When true (or when the campaign already has an interval), stagger sends
    #: instead of blasting every recipient immediately.
    paced: bool = False


class EnrollResponse(BaseModel):
    enrolled: int
    already_enrolled: int
    not_found: int
    sent: int = 0
    failed: int = 0
    suppressed: int = 0
    drafts_ready: int = 0
    drafts_generated: int = 0


class ProcessCampaignResponse(BaseModel):
    sent: int
    suppressed: int
    completed: int
    failed: int
    skipped_no_quota: bool


class PreviewRequest(BaseModel):
    contact_id: uuid.UUID
    step_number: int = Field(ge=1)


class PreviewResponse(BaseModel):
    subject: str
    body: str
    variables_filled: list[str]
    variables_empty: list[str]
    unrecognized_variables: list[str]


class CampaignReport(BaseModel):
    """Client-ready report (section 49), scoped to what's actually
    attributable to one campaign. Provider cost is workspace-level in this
    data model, not per-campaign, so it's deliberately not included here —
    see GET /analytics/overview for cost figures.

    Every *_rate field is null when its denominator is zero (nothing to
    divide by yet), never a guessed 0. positive_replies/positive_reply_rate
    specifically only count replies an AI provider actually classified as
    positive (see reply_sentiment_service.py) — a reply whose webhook
    payload carried no text, or arrived while no `ai` provider was enabled,
    stays unclassified and is not counted as positive, so this can
    understate the true rate but never overstate it."""

    campaign_id: uuid.UUID
    name: str
    status: CampaignStatus
    contacts_enrolled: int
    sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    positive_replies: int
    bounced: int
    unsubscribed: int
    meetings: int
    won: int
    delivery_rate: float | None
    bounce_rate: float | None
    open_rate: float | None
    click_rate: float | None
    reply_rate: float | None
    positive_reply_rate: float | None
