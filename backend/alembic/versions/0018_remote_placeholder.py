"""Placeholder for remote revision 0018 present in the imported dump.

The dump's alembic_version is 0018, but those intermediate migration files
are not in this checkout. This no-op revision lets local alembic locate
0018 so later migrations (e.g. email_setups) can apply cleanly.

Revision ID: 0018
Revises: 0013
Create Date: 2026-09-23

"""
from collections.abc import Sequence

revision: str = "0018"
down_revision: str | None = "0013"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
