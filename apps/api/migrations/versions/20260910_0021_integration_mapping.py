"""Create integration mapping and reconciliation foundation.

Revision ID: 20260910_0021
Revises: 20260910_0020
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0021"
down_revision: str | None = "20260910_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mapping_profiles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=140), nullable=False),
        sa.Column("source_type", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("current_version >= 0", name="ck_mapping_profiles_current_version"),
        sa.ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_mapping_profiles_connector_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "connector_id", "key", name="uq_mapping_profiles_connector_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_mapping_profiles_id_org"),
    )

    op.create_table(
        "mapping_profile_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("draft", "active", "retired", name="mappingversionstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("mapping_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_mapping_profile_versions_version"),
        sa.ForeignKeyConstraint(
            ["profile_id", "organization_id"],
            ["mapping_profiles.id", "mapping_profiles.organization_id"],
            name="fk_mapping_profile_versions_profile_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "version", name="uq_mapping_profile_versions_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_mapping_profile_versions_id_org"),
    )
    op.create_index("ix_mapping_profile_versions_org_status", "mapping_profile_versions", ["organization_id", "status"])

    op.create_table(
        "sync_checkpoints",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("stream_key", sa.String(length=160), nullable=False),
        sa.Column("cursor", sa.String(length=1024), nullable=True),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("advanced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("revision >= 1", name="ck_sync_checkpoints_revision"),
        sa.ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_sync_checkpoints_connector_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "connector_id", "stream_key", name="uq_sync_checkpoints_stream"),
    )

    op.create_table(
        "integration_conflicts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("external_type", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("internal_type", sa.String(length=120), nullable=True),
        sa.Column("internal_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.Enum("open", "resolved", "ignored", name="integrationconflictstatus", native_enum=False), nullable=False, server_default="open"),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column("source_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("internal_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolution", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_integration_conflicts_connector_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_conflicts_org_status", "integration_conflicts", ["organization_id", "status"])
    op.create_index("ix_integration_conflicts_source", "integration_conflicts", ["connector_id", "external_type", "external_id"])


def downgrade() -> None:
    op.drop_table("integration_conflicts")
    op.drop_table("sync_checkpoints")
    op.drop_table("mapping_profile_versions")
    op.drop_table("mapping_profiles")
