import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.providers.base import ProviderCategory
from app.schemas.contact import ContactRead


class SearchBatchCreate(BaseModel):
    """Manual empty batch — same SearchBatch row shape as Discover creates."""

    name: str = Field(min_length=1, max_length=255)


class SearchBatchRename(BaseModel):
    """Click-to-rename on the batch detail page, same convention as a
    Finder folder rename — name lives in criteria_snapshot["name"] like
    every other batch (see SearchBatchRead.name), not a new column."""

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
    #: The actual SMTP address for email_setup_id — EmailSetup is a
    #: separate table, so this can't be a plain from_attributes column;
    #: the listing endpoint fills it in via one batch-fetched lookup, not
    #: a query per row. None means no Email Setup is assigned to this
    #: batch yet.
    assigned_email: str | None = None
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
    #: Real counts across every campaign this batch's leads were ever
    #: emailed through — not stored on the batch, computed fresh on each
    #: read. `rejected` = the provider refused the message at send time
    #: (never even left, e.g. invalid address) — distinct from `bounced`,
    #: which means it was sent successfully and bounced afterward.
    emails_sent: int = 0
    bounced: int = 0
    rejected: int = 0
    #: bounced / sent — None (not 0%) until at least one email has been
    #: sent, so "no data yet" is never shown as if it were a real 0%.
    bounce_rate: float | None = None
    #: rejected / (sent + rejected) — None until at least one send was
    #: attempted.
    rejection_rate: float | None = None
    #: True while a scoring/email-reveal/phone-enrichment sweep is
    #: genuinely still running — a timestamp was set (auto right after
    #: search, or a manual "all" click) AND work is still outstanding.
    #: Reflects real server-side state, not anything client-local, so it
    #: reads correctly even after navigating away and back or reloading.
    scoring_active: bool = False
    email_enrichment_active: bool = False
    phone_enrichment_active: bool = False


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
    """Reveal runs as a background task — a real reveal() call is a live
    Apollo/Smartlead API request per contact, and a full batch's worth
    sequentially (measured: 72s for 100 contacts) is long enough to exceed
    typical proxy/tunnel timeouts if the HTTP request stayed open for all
    of it. So this reports what got scheduled, not final counts; poll the
    batch (already done via the batch page's refetchInterval) to see
    emails land."""

    scheduled: int
    already_revealed: int
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
