"""Create data portability and tenant export foundation.

Revision ID: 20260910_0014
Revises: 20260910_0013
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0014"
down_revision: str | None = "20260910_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXPORT_PERMISSIONS = (
    ("data.export.create", "data", "export", "create", "Request authorized tenant, project, or module data exports.", "high"),
    ("data.export.download", "data", "export", "download", "Download completed authorized data exports.", "high"),
    ("data.export.audit", "data", "export_audit", "include", "Include permitted audit history in a data export.", "critical"),
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
            for key, module, resource, action, description, risk in _EXPORT_PERMISSIONS
        ],
    )

    op.create_table(
        "data_export_requests",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("scope_type", sa.Enum("company", "project", "module", name="exportscopetype", native_enum=False), nullable=False),
        sa.Column("scope_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.Enum("queued", "running", "completed", "failed", "cancelled", "expired", name="exportstatus", native_enum=False), nullable=False, server_default="queued"),
        sa.Column("include_files", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("include_audit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manifest_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_file_asset_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("manifest_version >= 1", name="ck_data_export_requests_manifest_version"),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_data_export_requests_progress"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["output_file_asset_id", "organization_id"], ["file_assets.id", "file_assets.organization_id"], name="fk_data_export_requests_output_asset_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_data_export_requests_id_org"),
    )
    op.create_index("ix_data_export_requests_org_status", "data_export_requests", ["organization_id", "status"])

    op.create_table(
        "data_export_manifest_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("export_request_id", sa.Uuid(), nullable=False),
        sa.Column("module_key", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("record_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("record_count >= 0", name="ck_data_export_manifest_items_records"),
        sa.CheckConstraint("file_count >= 0", name="ck_data_export_manifest_items_files"),
        sa.CheckConstraint("schema_version >= 1", name="ck_data_export_manifest_items_schema_version"),
        sa.CheckConstraint("checksum_sha256 IS NULL OR length(checksum_sha256) = 64", name="ck_data_export_manifest_items_checksum"),
        sa.ForeignKeyConstraint(["export_request_id", "organization_id"], ["data_export_requests.id", "data_export_requests.organization_id"], name="fk_data_export_manifest_items_request_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("export_request_id", "relative_path", name="uq_data_export_manifest_items_path"),
    )
    op.create_index("ix_data_export_manifest_items_export_module", "data_export_manifest_items", ["export_request_id", "module_key"])


def downgrade() -> None:
    op.drop_table("data_export_manifest_items")
    op.drop_table("data_export_requests")
    op.execute("DELETE FROM permissions WHERE key IN ('data.export.create','data.export.download','data.export.audit')")
