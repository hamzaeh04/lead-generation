"""search_batches: email_setup + outreach tracking for auto draft/send

After a Discover batch finishes (emails revealed), the platform can
auto-generate AI drafts and send via an assigned SMTP Email Setup.
These columns record which mailbox/campaign were used and how far
the automation got.

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "search_batches",
        sa.Column("email_setup_id", sa.Uuid(as_uuid=True), sa.ForeignKey("email_setups.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "search_batches",
        sa.Column(
            "outreach_campaign_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "search_batches",
        sa.Column("outreach_status", sa.String(32), nullable=False, server_default="idle"),
    )


def downgrade() -> None:
    op.drop_column("search_batches", "outreach_status")
    op.drop_column("search_batches", "outreach_campaign_id")
    op.drop_column("search_batches", "email_setup_id")
