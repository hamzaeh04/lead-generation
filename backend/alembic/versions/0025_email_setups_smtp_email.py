"""Simplify email_setups columns to name/host/port/email/password/tls/default

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column("email_setups", sa.Column("smtp_email", sa.String(255), nullable=True))
    op.execute(
        """
        UPDATE email_setups
        SET smtp_email = lower(coalesce(nullif(smtp_from_email, ''), smtp_username))
        """
    )
    op.alter_column("email_setups", "smtp_email", nullable=False)
    op.drop_constraint("uq_email_setups_from_email", "email_setups", type_="unique")
    op.drop_column("email_setups", "smtp_username")
    op.drop_column("email_setups", "smtp_from_email")
    op.create_unique_constraint("uq_email_setups_smtp_email", "email_setups", ["smtp_email"])


def downgrade() -> None:
    op.drop_constraint("uq_email_setups_smtp_email", "email_setups", type_="unique")
    op.add_column("email_setups", sa.Column("smtp_username", sa.String(255), nullable=True))
    op.add_column("email_setups", sa.Column("smtp_from_email", sa.String(255), nullable=True))
    op.execute(
        """
        UPDATE email_setups
        SET smtp_username = smtp_email, smtp_from_email = smtp_email
        """
    )
    op.alter_column("email_setups", "smtp_username", nullable=False)
    op.alter_column("email_setups", "smtp_from_email", nullable=False)
    op.drop_column("email_setups", "smtp_email")
    op.create_unique_constraint("uq_email_setups_from_email", "email_setups", ["smtp_from_email"])
