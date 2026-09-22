import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contact import ContactRead


class CompanySourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    external_id: str | None
    source_url: str | None
    source_type: str
    retrieved_at: datetime


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    domain: str | None
    website: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    industry: str | None
    category: str | None
    employee_count: int | None
    annual_revenue: float | None
    founded_year: int | None
    description: str | None
    linkedin_url: str | None
    social_urls: dict[str, str]
    field_provenance: dict[str, Any]
    first_seen: datetime
    last_seen: datetime


class DecisionMakerSearchRequest(BaseModel):
    target_titles: list[str] = Field(
        default_factory=lambda: ["owner", "founder", "president", "ceo", "general manager"]
    )


class DecisionMakerSearchResponse(BaseModel):
    contacts_created: int
    contacts_matched: int
    contacts: list[ContactRead]
