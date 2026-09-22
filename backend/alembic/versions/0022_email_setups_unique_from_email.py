"""Unique smtp_from_email per workspace on email_setups

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-23

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # Normalize existing emails so the unique index is case-insensitive in practice
    # for already-stored rows (app layer always lowercases on write).
    op.execute("UPDATE email_setups SET smtp_from_email = lower(smtp_from_email)")
    op.create_unique_constraint(
        "uq_email_setups_workspace_from_email",
        "email_setups",
        ["workspace_id", "smtp_from_email"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_email_setups_workspace_from_email", "email_setups", type_="unique")
