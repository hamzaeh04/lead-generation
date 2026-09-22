"""workspace_api_keys — one provider-credentials row per workspace

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("apollo_api_key", sa.String(512), nullable=True),
        sa.Column("pdl_api_key", sa.String(512), nullable=True),
        sa.Column("serpapi_api_key", sa.String(512), nullable=True),
        sa.Column("apify_api_token", sa.String(512), nullable=True),
        sa.Column("phantombuster_api_key", sa.String(512), nullable=True),
        sa.Column("hunter_api_key", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_api_keys_workspace"),
    )
    op.create_index("ix_workspace_api_keys_workspace_id", "workspace_api_keys", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_api_keys_workspace_id", table_name="workspace_api_keys")
    op.drop_table("workspace_api_keys")
