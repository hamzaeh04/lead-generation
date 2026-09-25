"""Normalize provider_configs.provider to lowercase

A capitalised row like "Anthropic" never matches the factory builders
(which key on "anthropic"), so Discover prompt parsing reported
"no enabled AI provider has credentials" even when ANTHROPIC_API_KEY was set.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-26

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE provider_configs SET provider = lower(provider) "
        "WHERE provider <> lower(provider)"
    )


def downgrade() -> None:
    # Irreversible normalisation — casing was never semantically meaningful.
    pass
