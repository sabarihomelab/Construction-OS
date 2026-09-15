"""Create file and media foundation.

Revision ID: 20260910_0008
Revises: 20260910_0007
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0008"
down_revision: str | None = "20260910_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FILE_PERMISSIONS = (
    (
        "files.file.view",
        "files",
        "file",
        "view",
        "View file metadata and permitted attachments within the authorized scope.",
        "medium",
    ),
    (
        "files.file.download",
        "files",
        "file",
        "download",
        "Download permitted files and file versions within the authorized scope.",
        "medium",
    ),
    (
        "files.file.upload",
        "files",
        "file",
        "upload",
        "Upload and attach files within the authorized scope.",
        "medium",
    ),
    (
        "files.file.manage",
        "files",
        "file",
        "manage",
        "Manage file versions, retention, links, retirement, and controlled deletion.",
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
            for key, module, resource, action, description, risk in _FILE_PERMISSIONS
        ],
    )

    op.create_table(
        "storage_objects",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("original", "derivative", "temporary", name="storageobjectkind", native_enum=False),
            nullable=False,
        ),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "pending_delete", "deleted", name="storageobjectstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("size_bytes > 0", name="ck_storage_objects_size_positive"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_storage_objects_sha256_length"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_storage_objects_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_objects")),
        sa.UniqueConstraint("provider_key", "storage_key", name="uq_storage_objects_provider_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_storage_objects_id_org"),
        sa.UniqueConstraint(
            "organization_id", "sha256", "size_bytes", name="uq_storage_objects_org_hash_size"
        ),
    )
    op.create_index(op.f("ix_storage_objects_organization_id"), "storage_objects", ["organization_id"])
    op.create_index(op.f("ix_storage_objects_sha256"), "storage_objects", ["sha256"])
    op.create_index("ix_storage_objects_org_status", "storage_objects", ["organization_id", "status"])

    op.create_table(
        "organization_storage_usage",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("committed_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("object_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("committed_bytes >= 0", name="ck_storage_usage_committed_nonnegative"),
        sa.CheckConstraint("reserved_bytes >= 0", name="ck_storage_usage_reserved_nonnegative"),
        sa.CheckConstraint("object_count >= 0", name="ck_storage_usage_object_count_nonnegative"),
        sa.CheckConstraint("revision >= 1", name="ck_storage_usage_revision"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_storage_usage_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("organization_id", name=op.f("pk_organization_storage_usage")),
    )

    op.create_table(
        "file_assets",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "retired", "deleted", name="fileassetstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("current_version >= 1", name="ck_file_assets_current_version"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name=op.f("fk_file_assets_created_by_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_file_assets_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_assets")),
        sa.UniqueConstraint("id", "organization_id", name="uq_file_assets_id_org"),
    )
    op.create_index(op.f("ix_file_assets_organization_id"), "file_assets", ["organization_id"])

    op.create_table(
        "file_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("storage_object_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_content_type", sa.String(length=160), nullable=True),
        sa.Column("detected_content_type", sa.String(length=160), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "scan_status",
            sa.Enum("pending", "scanning", "clean", "quarantined", "failed", name="filescanstatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "processing_status",
            sa.Enum("pending", "processing", "ready", "failed", name="fileprocessingstatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "source_type",
            sa.Enum("user", "integration", "import", "system", name="filesourcetype", native_enum=False),
            nullable=False,
        ),
        sa.Column("source_system", sa.String(length=120), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("external_version", sa.String(length=255), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_file_versions_version"),
        sa.CheckConstraint("size_bytes > 0", name="ck_file_versions_size_positive"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_file_versions_sha256_length"),
        sa.ForeignKeyConstraint(
            ["asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_file_versions_asset_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_object_id", "organization_id"],
            ["storage_objects.id", "storage_objects.organization_id"],
            name="fk_file_versions_storage_object_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_file_versions_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name=op.f("fk_file_versions_created_by_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_versions")),
        sa.UniqueConstraint("asset_id", "version", name="uq_file_versions_asset_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_file_versions_id_org"),
        sa.UniqueConstraint(
            "asset_id", "version", "organization_id", name="uq_file_versions_asset_version_org"
        ),
    )
    op.create_index(op.f("ix_file_versions_organization_id"), "file_versions", ["organization_id"])
    op.create_index(op.f("ix_file_versions_asset_id"), "file_versions", ["asset_id"])
    op.create_index(op.f("ix_file_versions_storage_object_id"), "file_versions", ["storage_object_id"])
    op.create_index(op.f("ix_file_versions_sha256"), "file_versions", ["sha256"])

    op.create_table(
        "file_links",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=80), nullable=False, server_default="attachment"),
        sa.Column("pinned_version", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("pinned_version IS NULL OR pinned_version >= 1", name="ck_file_links_pinned_version"),
        sa.ForeignKeyConstraint(
            ["asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_file_links_asset_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "pinned_version", "organization_id"],
            ["file_versions.asset_id", "file_versions.version", "file_versions.organization_id"],
            name="fk_file_links_pinned_version_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_file_links_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name=op.f("fk_file_links_created_by_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_links")),
        sa.UniqueConstraint(
            "organization_id", "entity_type", "entity_id", "asset_id", "relation_type",
            name="uq_file_links_entity_asset_relation",
        ),
    )
    op.create_index(op.f("ix_file_links_organization_id"), "file_links", ["organization_id"])
    op.create_index(op.f("ix_file_links_asset_id"), "file_links", ["asset_id"])
    op.create_index("ix_file_links_org_entity", "file_links", ["organization_id", "entity_type", "entity_id"])

    op.create_table(
        "file_variants",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("file_version_id", sa.Uuid(), nullable=False),
        sa.Column("variant_key", sa.String(length=64), nullable=False),
        sa.Column("storage_object_id", sa.Uuid(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("width IS NULL OR width > 0", name="ck_file_variants_width_positive"),
        sa.CheckConstraint("height IS NULL OR height > 0", name="ck_file_variants_height_positive"),
        sa.ForeignKeyConstraint(
            ["file_version_id", "organization_id"],
            ["file_versions.id", "file_versions.organization_id"],
            name="fk_file_variants_file_version_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["storage_object_id", "organization_id"],
            ["storage_objects.id", "storage_objects.organization_id"],
            name="fk_file_variants_storage_object_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_file_variants_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_variants")),
        sa.UniqueConstraint("file_version_id", "variant_key", name="uq_file_variants_version_key"),
    )
    op.create_index(op.f("ix_file_variants_organization_id"), "file_variants", ["organization_id"])
    op.create_index(op.f("ix_file_variants_file_version_id"), "file_variants", ["file_version_id"])
    op.create_index(op.f("ix_file_variants_storage_object_id"), "file_variants", ["storage_object_id"])

    op.create_table(
        "upload_sessions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("temporary_storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_content_type", sa.String(length=160), nullable=True),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("created", "uploading", "uploaded", "finalized", "expired", "failed", name="uploadstatus", native_enum=False),
            nullable=False,
            server_default="created",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "expected_size_bytes IS NULL OR expected_size_bytes > 0",
            name="ck_upload_sessions_expected_size_positive",
        ),
        sa.CheckConstraint(
            "expected_sha256 IS NULL OR length(expected_sha256) = 64",
            name="ck_upload_sessions_expected_sha256_length",
        ),
        sa.CheckConstraint("reserved_bytes >= 0", name="ck_upload_sessions_reserved_bytes_nonnegative"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_upload_sessions_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_upload_sessions_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_sessions")),
        sa.UniqueConstraint("temporary_storage_key", name=op.f("uq_upload_sessions_temporary_storage_key")),
    )
    op.create_index(op.f("ix_upload_sessions_organization_id"), "upload_sessions", ["organization_id"])
    op.create_index(op.f("ix_upload_sessions_user_id"), "upload_sessions", ["user_id"])
    op.create_index(op.f("ix_upload_sessions_expires_at"), "upload_sessions", ["expires_at"])
    op.create_index("ix_upload_sessions_org_status", "upload_sessions", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_upload_sessions_org_status", table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_expires_at"), table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_user_id"), table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_organization_id"), table_name="upload_sessions")
    op.drop_table("upload_sessions")

    op.drop_index(op.f("ix_file_variants_storage_object_id"), table_name="file_variants")
    op.drop_index(op.f("ix_file_variants_file_version_id"), table_name="file_variants")
    op.drop_index(op.f("ix_file_variants_organization_id"), table_name="file_variants")
    op.drop_table("file_variants")

    op.drop_index("ix_file_links_org_entity", table_name="file_links")
    op.drop_index(op.f("ix_file_links_asset_id"), table_name="file_links")
    op.drop_index(op.f("ix_file_links_organization_id"), table_name="file_links")
    op.drop_table("file_links")

    op.drop_index(op.f("ix_file_versions_sha256"), table_name="file_versions")
    op.drop_index(op.f("ix_file_versions_storage_object_id"), table_name="file_versions")
    op.drop_index(op.f("ix_file_versions_asset_id"), table_name="file_versions")
    op.drop_index(op.f("ix_file_versions_organization_id"), table_name="file_versions")
    op.drop_table("file_versions")

    op.drop_index(op.f("ix_file_assets_organization_id"), table_name="file_assets")
    op.drop_table("file_assets")
    op.drop_table("organization_storage_usage")

    op.drop_index("ix_storage_objects_org_status", table_name="storage_objects")
    op.drop_index(op.f("ix_storage_objects_sha256"), table_name="storage_objects")
    op.drop_index(op.f("ix_storage_objects_organization_id"), table_name="storage_objects")
    op.drop_table("storage_objects")

    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE key IN "
            "('files.file.view','files.file.download','files.file.upload','files.file.manage')"
        )
    )
