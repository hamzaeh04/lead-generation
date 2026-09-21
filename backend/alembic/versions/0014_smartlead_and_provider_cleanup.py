"""smartlead provider + retire hunter/pdl/serpapi/osm/apify/phantombuster

The app now only sources leads via Apollo and Smartlead. This migration
deletes the registry rows for the retired providers, drops the two tables
that were 100% dedicated to a retired feature (Apify's actor_configs,
Hunter's email_verifications), and seeds a disabled smartlead/
person_discovery row. provider_usage (shared audit log) and the
provider_category Postgres enum are left untouched — the enum stays a
superset of what the Python ProviderCategory now exposes.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-20

"""
import uuid as uuid_module
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

provider_category = postgresql.ENUM(name="provider_category", create_type=False)
verification_status = postgresql.ENUM(
    "valid", "invalid", "risky", "unknown", name="verification_status", create_type=False
)

_REMOVED_PROVIDERS = (
    "hunter",
    "people_data_labs",
    "serpapi",
    "openstreetmap",
    "apify",
    "phantombuster",
)

# Exact rows being deleted, captured here for downgrade() —
# (provider, category, enabled, priority, monthly_free_quota).
_DELETED_ROWS = [
    ("people_data_labs", "company_discovery", False, 2, 100),
    ("people_data_labs", "person_discovery", False, 2, 100),
    ("serpapi", "local_business_discovery", False, 1, 250),
    ("apify", "local_business_discovery", False, 2, None),
    ("apify", "company_discovery", False, 2, None),
    ("phantombuster", "social_signal", False, 1, None),
    ("hunter", "email_finder", False, 1, 25),
    ("hunter", "email_verifier", False, 1, 50),
    ("openstreetmap", "local_business_discovery", True, 3, None),
]


def upgrade() -> None:
    placeholders = ",".join(repr(p) for p in _REMOVED_PROVIDERS)
    op.execute(f"DELETE FROM provider_configs WHERE provider IN ({placeholders})")

    op.drop_table("actor_configs")

    op.drop_table("email_verifications")
    verification_status.drop(op.get_bind(), checkfirst=True)

    provider_configs = sa.table(
        "provider_configs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("provider", sa.String),
        sa.column("category", provider_category),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.Integer),
    )
    op.bulk_insert(
        provider_configs,
        [
            {
                "id": uuid_module.uuid4(),
                "provider": "smartlead",
                "category": "person_discovery",
                "enabled": False,
                "priority": 2,
            }
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM provider_configs WHERE provider = 'smartlead'")

    verification_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("verification_status", verification_status, nullable=False),
        sa.Column("verification_score", sa.Integer(), nullable=True),
        sa.Column("mx_records", sa.Boolean(), nullable=True),
        sa.Column("smtp_check", sa.Boolean(), nullable=True),
        sa.Column("accept_all", sa.Boolean(), nullable=True),
        sa.Column("disposable", sa.Boolean(), nullable=True),
        sa.Column("free_provider", sa.Boolean(), nullable=True),
        sa.Column("role_account", sa.Boolean(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "verified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_email_verifications_workspace_contact",
        "email_verifications",
        ["workspace_id", "contact_id"],
    )

    op.create_table(
        "actor_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("category", provider_category, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_actor_configs_category", "actor_configs", ["category"])

    provider_configs = sa.table(
        "provider_configs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("provider", sa.String),
        sa.column("category", provider_category),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.Integer),
        sa.column("monthly_free_quota", sa.Integer),
    )
    op.bulk_insert(
        provider_configs,
        [
            {
                "id": uuid_module.uuid4(),
                "provider": provider,
                "category": category,
                "enabled": enabled,
                "priority": priority,
                "monthly_free_quota": quota,
            }
            for provider, category, enabled, priority, quota in _DELETED_ROWS
        ],
    )
