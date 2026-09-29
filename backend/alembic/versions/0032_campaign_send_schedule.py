"""campaigns: send_interval_minutes + send window for paced outreach

Enables one-email-at-a-time sending on a fixed interval (5–60 minutes)
only inside a daily local time window (e.g. 09:00–19:00).

Revision ID: 0032
Revises: 0031b
Create Date: 2026-09-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031b"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("send_interval_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("send_window_start", sa.String(length=5), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("send_window_end", sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "send_window_end")
    op.drop_column("campaigns", "send_window_start")
    op.drop_column("campaigns", "send_interval_minutes")
