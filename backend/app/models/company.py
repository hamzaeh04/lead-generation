from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical company entity. Every field may be null — a value is only
    ever set from an actual provider response, CSV import, or manual entry
    (see CompanySource for provenance of each contributing record, and
    field_provenance for per-field attribution)."""

    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_workspace_domain", "workspace_id", "domain"),
        Index("ix_companies_workspace_normalized_name", "workspace_id", "normalized_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    normalized_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Real numbers from a provider's organization enrichment (e.g. Apollo's
    #: reveal step) — never a parsed/estimated value from a band string.
    annual_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    social_urls: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)

    # Per-field provenance: {"name": {"provider": "apollo", "retrieved_at": "..."}, ...}
    field_provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sources: Mapped[list["CompanySource"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class CompanySource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provenance record: proof that a Company (or a subset of its fields)
    actually originated from a real provider response, CSV row, or manual
    entry. A company with zero CompanySource rows should not exist."""

    __tablename__ = "company_sources"
    __table_args__ = (Index("ix_company_sources_company_id", "company_id"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    raw_reference: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="sources")
