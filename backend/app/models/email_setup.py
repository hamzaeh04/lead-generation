from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EmailSetup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace SMTP account configuration.

    Mirrors the env SMTP_* knobs (host/port/username/password/from_email) so
    users can keep multiple senders per workspace, create them one-by-one, or
    bulk-import via CSV. Credentials are stored for outbound mail — never log
    smtp_password (see app.utils.logging._SENSITIVE_KEYS).
    """

    __tablename__ = "email_setups"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
