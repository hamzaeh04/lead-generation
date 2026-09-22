"""contacts.email_reveal_attempted — stop repeat-billing reveal clicks

Apollo's /people/match has no server-side memory of "already tried" for a
given person — calling it again for the same contact spends another
credit for the identical non-result. This column lets the Reveal button
(and the reveal endpoint itself) refuse a second attempt once the first
one already came back with no email, instead of letting a masked contact
with no available email get re-billed on every click.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("email_reveal_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("contacts", "email_reveal_attempted")
