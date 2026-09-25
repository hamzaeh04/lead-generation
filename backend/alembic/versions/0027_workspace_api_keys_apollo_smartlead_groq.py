"""workspace_api_keys: keep only apollo, smartlead, groq

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

_DROP = (
    "pdl_api_key",
    "serpapi_api_key",
    "apify_api_token",
    "phantombuster_api_key",
    "hunter_api_key",
)


def upgrade() -> None:
    for col in _DROP:
        op.drop_column("workspace_api_keys", col)
    op.add_column("workspace_api_keys", sa.Column("smartlead_api_key", sa.String(512), nullable=True))
    op.add_column("workspace_api_keys", sa.Column("groq_api_key", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace_api_keys", "groq_api_key")
    op.drop_column("workspace_api_keys", "smartlead_api_key")
    op.add_column("workspace_api_keys", sa.Column("pdl_api_key", sa.String(512), nullable=True))
    op.add_column("workspace_api_keys", sa.Column("serpapi_api_key", sa.String(512), nullable=True))
    op.add_column("workspace_api_keys", sa.Column("apify_api_token", sa.String(512), nullable=True))
    op.add_column("workspace_api_keys", sa.Column("phantombuster_api_key", sa.String(512), nullable=True))
    op.add_column("workspace_api_keys", sa.Column("hunter_api_key", sa.String(512), nullable=True))
