import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailSetupBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(min_length=1, max_length=255)
    smtp_from_email: EmailStr
    is_default: bool = False


class EmailSetupCreate(EmailSetupBase):
    smtp_password: str = Field(min_length=1, max_length=255)


class EmailSetupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    smtp_host: str | None = Field(default=None, min_length=1, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, min_length=1, max_length=255)
    smtp_password: str | None = Field(default=None, min_length=1, max_length=255)
    smtp_from_email: EmailStr | None = None
    is_default: bool | None = None


class EmailSetupRead(EmailSetupBase):
    """Password is never returned — only a flag that one is stored."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    has_password: bool = True
    created_at: datetime
    updated_at: datetime


class EmailSetupDefaults(BaseModel):
    """UI placeholder defaults (mirrors .env SMTP_* keys)."""

    name: str = "Primary SMTP"
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_username: str = "you@yourcompany.com"
    smtp_password: str = "your-smtp-password"
    smtp_from_email: str = "you@yourcompany.com"


class EmailSetupImportRowError(BaseModel):
    row_number: int
    message: str


class EmailSetupImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[EmailSetupImportRowError]
