import uuid

from pydantic import BaseModel


class SourceCount(BaseModel):
    provider: str
    count: int


class CampaignSummary(BaseModel):
    campaign_id: uuid.UUID
    name: str
    sent: int
    opened: int
    clicked: int
    replied: int
    bounced: int


class AnalyticsOverview(BaseModel):
    total_companies: int
    total_contacts: int
    verified_emails: int
    high_intent_leads: int
    high_icp_leads: int | None
    meetings: int
    conversions: int

    emails_sent: int
    delivered: int
    bounced: int
    opened: int
    clicked: int
    replied: int
    delivery_rate: float | None
    bounce_rate: float | None
    open_rate: float | None
    click_rate: float | None
    reply_rate: float | None
    positive_reply_rate: None = None  # not computable — no reply sentiment classification exists

    total_provider_cost: float
    cost_per_verified_lead: float | None
    cost_per_qualified_lead: float | None

    top_sources: list[SourceCount]
    top_campaigns: list[CampaignSummary]
