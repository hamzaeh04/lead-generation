"""Repair: create lead_qualifications if missing

The local dump advanced past 0019 without this table (0019 was
effectively skipped while email_setups migrations ran). Contact.list
paths selectinload qualifications and 500 without it.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text("SELECT to_regclass('public.lead_qualifications')")).scalar()
    if exists:
        return

    op.create_table(
        "lead_qualifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("score_version", sa.String(50), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(1), nullable=False),
        sa.Column("tier_rationale", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("overrides_triggered", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("disqualifier", sa.String(100), nullable=True),
        sa.Column("missing_data", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enrichment_priority", sa.String(20), nullable=True),
        sa.Column("recommended_channel", sa.String(20), nullable=True),
        sa.Column("recommended_angle", sa.Text(), nullable=True),
        sa.Column("objection_to_expect", sa.Text(), nullable=True),
        sa.Column("estimated_deal_band", sa.String(20), nullable=True),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("human_review_reason", sa.Text(), nullable=True),
        sa.Column("uncertainty_notes", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_lead_qualifications_contact_scored_at", "lead_qualifications", ["contact_id", "scored_at"]
    )
    op.create_index("ix_lead_qualifications_workspace_id", "lead_qualifications", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("lead_qualifications")
