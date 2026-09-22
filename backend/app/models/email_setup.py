from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EmailSetup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global SMTP account configuration (not workspace-scoped).

    Columns: name, smtp_host, smtp_port, smtp_email, smtp_password,
    smtp_use_tls, is_default, created_at, updated_at.
    smtp_email is unique globally. Never log smtp_password.
    """

    __tablename__ = "email_setups"
    __table_args__ = (UniqueConstraint("smtp_email", name="uq_email_setups_smtp_email"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_email: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
