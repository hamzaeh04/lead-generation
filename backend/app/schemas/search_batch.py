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
    qualified: int
    skipped: int
    failed: int
    total: int
