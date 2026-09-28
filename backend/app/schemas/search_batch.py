import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.providers.base import ProviderCategory
from app.schemas.contact import ContactRead


class SearchBatchCreate(BaseModel):
    """Manual empty batch — same SearchBatch row shape as Discover creates."""

    name: str = Field(min_length=1, max_length=255)


class SearchBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    provider: str
    category: ProviderCategory
    criteria_snapshot: dict[str, Any]
    companies_created: int
    companies_matched: int
    contacts_created: int
    contacts_matched: int
    email_setup_id: uuid.UUID | None = None
    outreach_campaign_id: uuid.UUID | None = None
    outreach_status: str = "idle"
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> str | None:
        raw = (self.criteria_snapshot or {}).get("name")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> str | None:
        raw = (self.criteria_snapshot or {}).get("description")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None


class SearchBatchDetail(SearchBatchRead):
    contacts: list[ContactRead]


class BatchQualifyResponse(BaseModel):
    """Qualification runs as a background task — a real qualify() call can
    take 30-40+ seconds each, long enough to exceed typical proxy/tunnel
    timeouts if the HTTP request stayed open for the whole batch. So this
    reports what got scheduled, not final counts; poll the batch (already
    done via the batch page's refetchInterval) to see scores land."""

    scheduled: int
    already_scored: int
    total: int


class BatchRevealResponse(BaseModel):
    revealed: int
    skipped: int
    failed: int
    total: int


class BatchPhoneEnrichResponse(BaseModel):
    """Requesting a phone reveal only kicks off Apollo's async lookup —
    the number itself lands later via webhook (see
    app/api/v1/webhooks.py's /apollo/phone-reveal), so this reports what
    got requested, not how many numbers were actually found."""

    requested: int
    skipped: int
    failed: int
    total: int
