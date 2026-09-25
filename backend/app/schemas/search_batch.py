import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.providers.base import ProviderCategory
from app.schemas.contact import ContactRead


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
    created_at: datetime


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
