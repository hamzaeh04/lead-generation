"""contacts: person location + per-result firmographic fields

Smartlead's SmartProspect search reports a person's own city/state/country
plus industry/sub-industry/company headcount/revenue bands alongside each
result — previously discarded entirely. These are stored on Contact (not
Company) because they're reported per search result, not independently
enriched onto the company record; bands are kept as-is (e.g. "$1 - 10M")
rather than parsed into a single number, since that would fabricate false
precision the provider never gave us.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

_COLUMNS = [
    ("city", sa.String(255)),
    ("state", sa.String(255)),
    ("country", sa.String(255)),
    ("industry", sa.String(255)),
    ("sub_industry", sa.String(255)),
    ("company_headcount", sa.String(50)),
    ("company_revenue", sa.String(50)),
]


def upgrade() -> None:
    for name, col_type in _COLUMNS:
        op.add_column("contacts", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("contacts", name)
