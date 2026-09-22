"""email_setups — workspace SMTP account configurations

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.create_table(
        "email_setups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("smtp_host", sa.String(255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_username", sa.String(255), nullable=False),
        sa.Column("smtp_password", sa.String(255), nullable=False),
        sa.Column("smtp_from_email", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_setups_workspace_id", "email_setups", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_email_setups_workspace_id", table_name="email_setups")
    op.drop_table("email_setups")
