"""search_batches: name + description for manually created batches

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "search_batches",
        sa.Column("name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "search_batches",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_batches", "description")
    op.drop_column("search_batches", "name")
