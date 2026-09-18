"""Create data governance and lifecycle foundation.

Revision ID: 20260910_0018
Revises: 20260910_0017
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0018"
down_revision: str | None = "20260910_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GOVERNANCE_PERMISSIONS = (
    ("data.governance.view", "data", "governance", "view", "View retention, legal hold and lifecycle policies.", "high"),
    ("data.governance.manage", "data", "governance", "manage", "Create and publish retention and legal-hold configuration.", "critical"),
    ("data.lifecycle.execute", "data", "lifecycle", "execute", "Execute approved archival or deletion lifecycle actions.", "critical"),
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
            {"key": key, "module": module, "resource": resource, "action": action, "description": description, "risk": risk, "is_active": True}
            for key, module, resource, action, description, risk in _GOVERNANCE_PERMISSIONS
        ],
    )

    op.create_table(
        "data_lifecycle_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("current_version >= 0", name="ck_data_lifecycle_policies_current_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_data_lifecycle_policies_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_data_lifecycle_policies_id_org"),
    )

    op.create_table(
        "data_lifecycle_policy_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("draft", "active", "retired", name="policyversionstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("classification", sa.Enum("internal", "confidential", "restricted", name="dataclassification", native_enum=False), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("disposition_action", sa.Enum("archive", "delete", "review", name="dispositionaction", native_enum=False), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_data_lifecycle_policy_versions_version"),
        sa.CheckConstraint("retention_days >= 0", name="ck_data_lifecycle_policy_versions_retention_days"),
        sa.ForeignKeyConstraint(["policy_id", "organization_id"], ["data_lifecycle_policies.id", "data_lifecycle_policies.organization_id"], name="fk_data_lifecycle_policy_versions_policy_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", "version", name="uq_data_lifecycle_policy_versions_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_data_lifecycle_policy_versions_id_org"),
    )
    op.create_index("ix_data_lifecycle_policy_versions_org_status", "data_lifecycle_policy_versions", ["organization_id", "status"])

    op.create_table(
        "legal_holds",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("hold_key", sa.String(length=140), nullable=False),
        sa.Column("scope_type", sa.String(length=80), nullable=False),
        sa.Column("scope_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.Enum("active", "released", name="legalholdstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "hold_key", name="uq_legal_holds_org_key"),
    )
    op.create_index("ix_legal_holds_org_scope_status", "legal_holds", ["organization_id", "scope_type", "scope_id", "status"])

    op.create_table(
        "lifecycle_runs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=80), nullable=False),
        sa.Column("scope_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.Enum("draft", "analyzing", "ready", "applying", "completed", "blocked", "failed", "cancelled", name="lifecyclerunstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("initiated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("candidate_count >= 0", name="ck_lifecycle_runs_candidate_count"),
        sa.CheckConstraint("blocked_count >= 0", name="ck_lifecycle_runs_blocked_count"),
        sa.CheckConstraint("applied_count >= 0", name="ck_lifecycle_runs_applied_count"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_version_id", "organization_id"], ["data_lifecycle_policy_versions.id", "data_lifecycle_policy_versions.organization_id"], name="fk_lifecycle_runs_policy_version_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lifecycle_runs_org_status", "lifecycle_runs", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_table("lifecycle_runs")
    op.drop_table("legal_holds")
    op.drop_table("data_lifecycle_policy_versions")
    op.drop_table("data_lifecycle_policies")
    op.execute("DELETE FROM permissions WHERE key IN ('data.governance.view','data.governance.manage','data.lifecycle.execute')")
