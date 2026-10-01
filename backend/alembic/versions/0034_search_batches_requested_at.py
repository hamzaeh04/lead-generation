"""search_batches: qualify/reveal/phone_enrich requested_at timestamps

Lets the API report whether a scoring/email-reveal/phone-enrichment sweep
is genuinely still running (timestamp set AND work still outstanding),
independent of any frontend tab being open or navigated away from.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "search_batches",
        sa.Column("qualify_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_batches",
        sa.Column("reveal_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_batches",
        sa.Column("phone_enrich_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_batches", "phone_enrich_requested_at")
    op.drop_column("search_batches", "reveal_requested_at")
    op.drop_column("search_batches", "qualify_requested_at")
