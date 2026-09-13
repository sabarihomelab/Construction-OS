"""Create reporting and analytics foundation.

Revision ID: 20260910_0016
Revises: 20260910_0015
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0016"
down_revision: str | None = "20260910_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("dataset_key", sa.String(length=140), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("visibility", sa.Enum("private", "shared", name="viewvisibility", native_enum=False), nullable=False, server_default="private"),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_saved_views_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "owner_user_id", "name", "dataset_key", name="uq_saved_views_owner_name_dataset"),
    )
    op.create_index("ix_saved_views_org_dataset", "saved_views", ["organization_id", "dataset_key"])

    op.create_table(
        "report_definitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_key", sa.String(length=140), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("current_version >= 0", name="ck_report_definitions_current_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_report_definitions_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_report_definitions_id_org"),
    )
    op.create_index("ix_report_definitions_org_dataset", "report_definitions", ["organization_id", "dataset_key"])

    op.create_table(
        "report_definition_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("draft", "active", "retired", name="reportversionstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("query_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("presentation_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_report_definition_versions_version"),
        sa.ForeignKeyConstraint(["definition_id", "organization_id"], ["report_definitions.id", "report_definitions.organization_id"], name="fk_report_definition_versions_definition_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "version", name="uq_report_definition_versions_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_report_definition_versions_id_org"),
    )
    op.create_index("ix_report_definition_versions_org_status", "report_definition_versions", ["organization_id", "status"])

    op.create_table(
        "report_runs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("report_version_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("queued", "running", "completed", "failed", "cancelled", name="reportrunstatus", native_enum=False), nullable=False, server_default="queued"),
        sa.Column("output_format", sa.Enum("pdf", "xlsx", "csv", name="reportoutputformat", native_enum=False), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_file_asset_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_report_runs_progress"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_version_id", "organization_id"], ["report_definition_versions.id", "report_definition_versions.organization_id"], name="fk_report_runs_version_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["output_file_asset_id", "organization_id"], ["file_assets.id", "file_assets.organization_id"], name="fk_report_runs_output_asset_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_runs_org_status", "report_runs", ["organization_id", "status"])

    op.create_table(
        "dashboard_definitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_dashboard_definitions_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_dashboard_definitions_org_key"),
    )


def downgrade() -> None:
    op.drop_table("dashboard_definitions")
    op.drop_table("report_runs")
    op.drop_table("report_definition_versions")
    op.drop_table("report_definitions")
    op.drop_table("saved_views")
