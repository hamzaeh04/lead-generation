"""Widen lead_qualifications.disqualifier from VARCHAR(100) to TEXT

The AI routinely writes a full explanatory sentence here (e.g.
"REGULATORY — Lead is employed by ..."), not a bare category name, so a
100-char cap made every verbose hard-disqualification fail to save with
StringDataRightTruncationError.

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.alter_column(
        "lead_qualifications",
        "disqualifier",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "lead_qualifications",
        "disqualifier",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
