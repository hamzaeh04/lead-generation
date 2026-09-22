"""Make email_setups global — drop workspace_id

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-23

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # Keep one row per from-email before enforcing a global unique constraint.
    op.execute(
        """
        DELETE FROM email_setups a
        USING email_setups b
        WHERE a.smtp_from_email = b.smtp_from_email
          AND a.ctid < b.ctid
        """
    )
    op.drop_constraint("uq_email_setups_workspace_from_email", "email_setups", type_="unique")
    op.drop_index("ix_email_setups_workspace_id", table_name="email_setups")
    op.drop_constraint("email_setups_workspace_id_fkey", "email_setups", type_="foreignkey")
    op.drop_column("email_setups", "workspace_id")
    op.create_unique_constraint("uq_email_setups_from_email", "email_setups", ["smtp_from_email"])


def downgrade() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    op.drop_constraint("uq_email_setups_from_email", "email_setups", type_="unique")
    op.add_column(
        "email_setups",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE email_setups
        SET workspace_id = (SELECT id FROM workspaces ORDER BY created_at LIMIT 1)
        WHERE workspace_id IS NULL
        """
    )
    op.alter_column("email_setups", "workspace_id", nullable=False)
    op.create_foreign_key(
        "email_setups_workspace_id_fkey",
        "email_setups",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_email_setups_workspace_id", "email_setups", ["workspace_id"])
    op.create_unique_constraint(
        "uq_email_setups_workspace_from_email",
        "email_setups",
        ["workspace_id", "smtp_from_email"],
    )
