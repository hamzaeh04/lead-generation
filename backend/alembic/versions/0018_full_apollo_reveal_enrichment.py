"""contacts.email_status + companies.annual_revenue/founded_year

Apollo's /people/match (reveal) returns far more than email/phone/name:
real deliverability status, precise employee count, precise revenue, and
company founding year. This adds the columns needed to keep that data
instead of discarding it — see LeadRevealService and apollo_provider.py's
expanded reveal() mapping.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("email_status", sa.String(50), nullable=True))
    op.add_column("companies", sa.Column("annual_revenue", sa.Float(), nullable=True))
    op.add_column("companies", sa.Column("founded_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "founded_year")
    op.drop_column("companies", "annual_revenue")
    op.drop_column("contacts", "email_status")
