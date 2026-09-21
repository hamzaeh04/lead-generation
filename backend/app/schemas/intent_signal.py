import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.intent_signal import IntentSignalType


class IntentSignalCreate(BaseModel):
    signal_type: IntentSignalType
    source: str
    source_url: str
    signal_text: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    detected_at: datetime | None = None


class IntentSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    signal_type: IntentSignalType
    provider: str
    source: str
    source_url: str
    signal_text: str | None
    confidence: float | None
    detected_at: datetime


class IntentScoreRead(BaseModel):
    company_id: uuid.UUID
    score: int
    signal_count: int
    signals: list[IntentSignalRead]
