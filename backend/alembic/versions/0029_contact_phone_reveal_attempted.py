"""contacts.phone_reveal_attempted — stop repeat-requesting Apollo phone reveal

Same reasoning as 0017's email_reveal_attempted: Apollo's async phone
reveal (POST /people/match with reveal_phone_number=true) has no
server-side memory of "already tried" for a given person, and only
charges credits when a number is actually found — but a contact Apollo
genuinely has no mobile number for would otherwise get re-requested every
time "Enrich phones" is clicked, for nothing.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("phone_reveal_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("contacts", "phone_reveal_attempted")
