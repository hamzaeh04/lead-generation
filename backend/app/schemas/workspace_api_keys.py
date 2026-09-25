import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceApiKeysUpsert(BaseModel):
    """Create or update the single API-keys row for a workspace.

    Empty / omitted fields leave the stored value unchanged on update.
    On first create, empty fields stay null.
    """

    apollo_api_key: str | None = Field(default=None, max_length=512)
    smartlead_api_key: str | None = Field(default=None, max_length=512)
    anthropic_api_key: str | None = Field(default=None, max_length=512)


class WorkspaceApiKeysRead(BaseModel):
    """Secrets are never returned — only whether each key is set."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    has_apollo_api_key: bool = False
    has_smartlead_api_key: bool = False
    has_anthropic_api_key: bool = False
    created_at: datetime
    updated_at: datetime


class WorkspaceApiKeysDefaults(BaseModel):
    """UI placeholders matching .env provider key names."""

    apollo_api_key: str = "your-apollo-api-key"
    smartlead_api_key: str = "your-smartlead-api-key"
    anthropic_api_key: str = "your-anthropic-api-key"
