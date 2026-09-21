import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.providers.base import ProviderCategory
from app.schemas.company import CompanyRead
from app.schemas.contact import ContactRead


class DiscoveryCriteriaSchema(BaseModel):
    keywords: str | None = None
    industry: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    company_name: str | None = None
    domain: str | None = None
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    job_titles: list[str] = Field(default_factory=list)
    seniorities: list[str] = Field(default_factory=list)
    limit: int = Field(default=25, ge=1, le=100)
    #: Smartlead-specific: the campaign to pull existing leads from.
    campaign_id: str | None = None
    #: Passthrough filters a specific provider understands (e.g. Smartlead's
    #: emailStatus) but that don't warrant a first-class field here.
    extra_filters: dict[str, Any] = Field(default_factory=dict)


class SearchExecuteRequest(BaseModel):
    workspace_id: uuid.UUID
    provider: str
    category: ProviderCategory
    criteria: DiscoveryCriteriaSchema


class SearchExecuteResponse(BaseModel):
    provider: str
    category: ProviderCategory
    #: None when the search returned nothing — no batch is created for a
    #: zero-result run, so the Leads page never fills up with empty ones.
    batch_id: uuid.UUID | None
    companies_created: int
    companies_matched: int
    contacts_created: int
    contacts_matched: int
    companies: list[CompanyRead]
    contacts: list[ContactRead]


class ParsePromptRequest(BaseModel):
    workspace_id: uuid.UUID
    provider: str
    prompt: str


class ParsePromptResponse(BaseModel):
    criteria: DiscoveryCriteriaSchema
