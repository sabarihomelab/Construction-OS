"""Create tenancy and identity foundation.

Revision ID: 20260910_0001
Revises:
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=False)
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "organization_settings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=35), nullable=False, server_default="en-US"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column(
            "unit_system",
            sa.Enum("metric", "imperial", "mixed", name="unitsystem", native_enum=False),
            nullable=False,
            server_default="metric",
        ),
        sa.Column(
            "time_format",
            sa.Enum("12h", "24h", name="timeformat", native_enum=False),
            nullable=False,
            server_default="24h",
        ),
        sa.Column("first_day_of_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("settings_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "first_day_of_week BETWEEN 1 AND 7", name="ck_organization_settings_first_day"
        ),
        sa.CheckConstraint(
            "settings_version >= 1", name="ck_organization_settings_settings_version"
        ),
        sa.CheckConstraint(
            "storage_quota_bytes IS NULL OR storage_quota_bytes > 0",
            name="ck_organization_settings_storage_quota",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_settings_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organization_id", name=op.f("pk_organization_settings")),
    )

    op.create_table(
        "users",
        sa.Column("primary_email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("identity_provider", sa.String(length=64), nullable=True),
        sa.Column("identity_subject", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", "disabled", name="userstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("identity_provider", "identity_subject", name="uq_users_identity"),
    )
    op.create_index(
        "uq_users_primary_email_lower",
        "users",
        [sa.text("lower(primary_email)")],
        unique=True,
    )

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=35), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("time_format", sa.String(length=3), nullable=True),
        sa.Column("date_format", sa.String(length=32), nullable=True),
        sa.Column("number_format", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "time_format IS NULL OR time_format IN ('12h', '24h')",
            name="ck_user_preferences_time_format",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_preferences")),
    )

    op.create_table(
        "organization_memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("internal", "external", "service", name="membershipkind", native_enum=False),
            nullable=False,
            server_default="internal",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "invited",
                "active",
                "suspended",
                "ended",
                name="membershipstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="invited",
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_organization_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_memberships")),
        sa.UniqueConstraint(
            "organization_id", "user_id", name="uq_organization_memberships_org_user"
        ),
    )
    op.create_index(
        op.f("ix_organization_memberships_organization_id"),
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_memberships_user_id"),
        "organization_memberships",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_memberships_user_id"), table_name="organization_memberships")
    op.drop_index(
        op.f("ix_organization_memberships_organization_id"),
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")
    op.drop_table("user_preferences")
    op.drop_index("uq_users_primary_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("organization_settings")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_table("organizations")
