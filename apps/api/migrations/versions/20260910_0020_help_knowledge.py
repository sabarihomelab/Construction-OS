"""Create tenant help and knowledge foundation.

Revision ID: 20260910_0020
Revises: 20260910_0019
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0020"
down_revision: str | None = "20260910_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        [{"key": "help.knowledge.manage", "module": "help", "resource": "knowledge", "action": "manage", "description": "Manage company-specific help and knowledge sources.", "risk": "high", "is_active": True}],
    )

    op.create_table(
        "tenant_knowledge_sources",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=140), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("kind", sa.Enum("file", "configuration", "manual", name="knowledgesourcekind", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("pending", "indexing", "ready", "failed", "retired", name="knowledgesourcestatus", native_enum=False), nullable=False, server_default="pending"),
        sa.Column("file_asset_id", sa.Uuid(), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("required_permission_key", sa.String(length=140), nullable=True),
        sa.Column("scope_type", sa.String(length=40), nullable=True),
        sa.Column("scope_id", sa.String(length=160), nullable=True),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_summary", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source_version >= 1", name="ck_tenant_knowledge_sources_source_version"),
        sa.CheckConstraint("(scope_type IS NULL AND scope_id IS NULL) OR (scope_type IS NOT NULL AND scope_id IS NOT NULL)", name="ck_tenant_knowledge_sources_scope_pair"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["required_permission_key"], ["permissions.key"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["file_asset_id", "organization_id"], ["file_assets.id", "file_assets.organization_id"], name="fk_tenant_knowledge_sources_file_asset_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_tenant_knowledge_sources_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_tenant_knowledge_sources_id_org"),
    )
    op.create_index("ix_tenant_knowledge_sources_org_status", "tenant_knowledge_sources", ["organization_id", "status"])

    op.create_table(
        "tenant_knowledge_chunks",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source_version >= 1", name="ck_tenant_knowledge_chunks_source_version"),
        sa.CheckConstraint("ordinal >= 0", name="ck_tenant_knowledge_chunks_ordinal"),
        sa.CheckConstraint("character_count >= 0", name="ck_tenant_knowledge_chunks_character_count"),
        sa.ForeignKeyConstraint(["source_id", "organization_id"], ["tenant_knowledge_sources.id", "tenant_knowledge_sources.organization_id"], name="fk_tenant_knowledge_chunks_source_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "source_version", "ordinal", name="uq_tenant_knowledge_chunks_version_ordinal"),
    )
    op.create_index("ix_tenant_knowledge_chunks_org_source", "tenant_knowledge_chunks", ["organization_id", "source_id"])


def downgrade() -> None:
    op.drop_table("tenant_knowledge_chunks")
    op.drop_table("tenant_knowledge_sources")
    op.execute("DELETE FROM permissions WHERE key = 'help.knowledge.manage'")
