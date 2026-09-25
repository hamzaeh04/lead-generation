from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class WorkspaceApiKeys(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Exactly one provider-credentials row per workspace.

    Mirrors the live provider keys: Apollo, Smartlead, Anthropic. Users create
    once and update in place — never more than one record per workspace.
    """

    __tablename__ = "workspace_api_keys"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_workspace_api_keys_workspace"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    apollo_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    smartlead_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    anthropic_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
