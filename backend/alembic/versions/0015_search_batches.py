"""search_batches — group Discover search results by run

Every /search/execute call now creates one search_batches row (with a
per-workspace sequence number for the "Batch 01" style UI) plus one
search_batch_contacts link per contact the run touched, so the Leads page
can list results by the run that found them instead of one flat list.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

provider_category = postgresql.ENUM(name="provider_category", create_type=False)


def upgrade() -> None:
    op.create_table(
        "search_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("category", provider_category, nullable=False),
        sa.Column("criteria_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("companies_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contacts_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contacts_matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_search_batches_workspace_sequence", "search_batches", ["workspace_id", "sequence"]
    )

    op.create_table(
        "search_batch_contacts",
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_batches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("is_new", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_search_batch_contacts_contact_id", "search_batch_contacts", ["contact_id"]
    )


def downgrade() -> None:
    op.drop_table("search_batch_contacts")
    op.drop_table("search_batches")
