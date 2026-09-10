"""Create guided setup and configuration template foundation.

Revision ID: 20260910_0013
Revises: 20260910_0012
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0013"
down_revision: str | None = "20260910_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETUP_PERMISSIONS = (
    (
        "admin.setup.view",
        "admin",
        "setup",
        "view",
        "View guided setup, configuration templates, and configuration health.",
        "medium",
    ),
    (
        "admin.setup.manage",
        "admin",
        "setup",
        "manage",
        "Create, publish, validate, and apply company configuration templates.",
        "high",
    ),
)


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("risk", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": module,
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, module, resource, action, description, risk in _SETUP_PERMISSIONS
        ],
    )

    op.create_table(
        "configuration_templates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("current_version >= 0", name="ck_configuration_templates_current_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_configuration_templates_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_configuration_templates_id_org"),
    )
    op.create_index("ix_configuration_templates_org_target", "configuration_templates", ["organization_id", "target_type"])

    op.create_table(
        "configuration_template_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "retired", name="templateversionstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_configuration_template_versions_version"),
        sa.ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["configuration_templates.id", "configuration_templates.organization_id"],
            name="fk_configuration_template_versions_template_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version", name="uq_configuration_template_versions_template_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_configuration_template_versions_id_org"),
    )
    op.create_index("ix_configuration_template_versions_org_status", "configuration_template_versions", ["organization_id", "status"])

    op.create_table(
        "setup_runs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("setup_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=160), nullable=True),
        sa.Column("template_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "validating", "ready", "applying", "completed", "failed", "cancelled", name="setuprunstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(length=120), nullable=True),
        sa.Column("validation_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("initiated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("revision >= 1", name="ck_setup_runs_revision"),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_setup_runs_progress"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["template_version_id", "organization_id"],
            ["configuration_template_versions.id", "configuration_template_versions.organization_id"],
            name="fk_setup_runs_template_version_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_setup_runs_org_status", "setup_runs", ["organization_id", "status"])

    op.create_table(
        "configuration_health_checks",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("check_key", sa.String(length=140), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=160), nullable=False, server_default="organization"),
        sa.Column(
            "status",
            sa.Enum("healthy", "attention", "blocked", "not_applicable", name="configurationhealthstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "check_key", "target_type", "target_id", name="uq_configuration_health_checks_target"),
    )
    op.create_index("ix_configuration_health_checks_org_status", "configuration_health_checks", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_table("configuration_health_checks")
    op.drop_table("setup_runs")
    op.drop_table("configuration_template_versions")
    op.drop_table("configuration_templates")
    op.execute("DELETE FROM permissions WHERE key IN ('admin.setup.view','admin.setup.manage')")
