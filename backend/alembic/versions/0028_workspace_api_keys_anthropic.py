"""workspace_api_keys: rename groq_api_key -> anthropic_api_key

Groq was fully removed this session (its free tier's per-minute
output-token cap made batch qualification impractically slow) and
replaced outright by Anthropic — see provider_factory.py. The per-
workspace credentials column follows the same swap rather than leaving
a dead groq_api_key column alongside a new one.

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-25
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.alter_column("workspace_api_keys", "groq_api_key", new_column_name="anthropic_api_key")


def downgrade() -> None:
    op.alter_column("workspace_api_keys", "anthropic_api_key", new_column_name="groq_api_key")
