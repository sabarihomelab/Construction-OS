"""Add project document control and specifications.

Revision ID: 20260910_0023
Revises: 20260910_0022
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0023"
down_revision: str | None = "20260910_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("documents.document.view", "documents", "document", "view", "View project documents and issued revisions within the authorized project scope.", "medium"),
    ("documents.document.create", "documents", "document", "create", "Create managed documents and draft revisions within the authorized project scope.", "medium"),
    ("documents.document.publish", "documents", "document", "publish", "Publish and supersede controlled document revisions within the authorized project scope.", "high"),
    ("documents.document.manage", "documents", "document", "manage", "Manage document folders, metadata, specifications, archival and document control.", "high"),
)


def upgrade() -> None:
    op.create_table(
        "document_folders",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_document_folders_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id", "organization_id"], ["document_folders.id", "document_folders.organization_id"], name="fk_document_folders_parent_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_document_folders"),
        sa.UniqueConstraint("id", "organization_id", name="uq_document_folders_id_org"),
        sa.UniqueConstraint("project_id", "parent_id", "name", name="uq_document_folders_parent_name"),
    )
    op.create_index("ix_document_folders_project_parent", "document_folders", ["project_id", "parent_id"], unique=False)
    op.create_index("ix_document_folders_organization_id", "document_folders", ["organization_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("folder_id", sa.Uuid(), nullable=True),
        sa.Column("number", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.Enum("general", "specification", "contract", "procedure", "closeout", "other", name="documentkind", native_enum=False), nullable=False, server_default="general"),
        sa.Column("status", sa.Enum("draft", "active", "archived", name="documentstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("discipline_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("current_revision_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_documents_version"),
        sa.CheckConstraint("current_revision_sequence >= 0", name="ck_documents_current_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_documents_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id", "organization_id"], ["document_folders.id", "document_folders.organization_id"], name="fk_documents_folder_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_documents_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("id", "organization_id", name="uq_documents_id_org"),
        sa.UniqueConstraint("project_id", "number", name="uq_documents_project_number"),
    )
    op.create_index("ix_documents_project_kind_status", "documents", ["project_id", "kind", "status"], unique=False)
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"], unique=False)
    op.create_index("ix_documents_project_id", "documents", ["project_id"], unique=False)

    op.create_table(
        "document_revisions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("revision_label", sa.String(length=80), nullable=False),
        sa.Column("file_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum("draft", "published", "superseded", "void", name="documentrevisionstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("sequence >= 1", name="ck_document_revisions_sequence"),
        sa.ForeignKeyConstraint(["document_id", "organization_id"], ["documents.id", "documents.organization_id"], name="fk_document_revisions_document_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_version_id", "organization_id"], ["file_versions.id", "file_versions.organization_id"], name="fk_document_revisions_file_version_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_document_revisions_created_by_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], name="fk_document_revisions_published_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_document_revisions"),
        sa.UniqueConstraint("id", "organization_id", name="uq_document_revisions_id_org"),
        sa.UniqueConstraint("document_id", "sequence", name="uq_document_revisions_document_sequence"),
        sa.UniqueConstraint("document_id", "revision_label", name="uq_document_revisions_document_label"),
    )
    op.create_index("ix_document_revisions_document_status", "document_revisions", ["document_id", "status"], unique=False)
    op.create_index("ix_document_revisions_organization_id", "document_revisions", ["organization_id"], unique=False)
    op.create_index("ix_document_revisions_file_version_id", "document_revisions", ["file_version_id"], unique=False)

    op.create_table(
        "specification_sections",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("section_number", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("division_code", sa.String(length=40), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="ck_specification_sections_version"),
        sa.CheckConstraint("page_start IS NULL OR page_start >= 1", name="ck_specification_sections_page_start"),
        sa.CheckConstraint("page_end IS NULL OR page_end >= 1", name="ck_specification_sections_page_end"),
        sa.ForeignKeyConstraint(["document_id", "organization_id"], ["documents.id", "documents.organization_id"], name="fk_specification_sections_document_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_specification_sections"),
        sa.UniqueConstraint("id", "organization_id", name="uq_specification_sections_id_org"),
        sa.UniqueConstraint("document_id", "section_number", name="uq_specification_sections_number"),
    )
    op.create_index("ix_specification_sections_document_number", "specification_sections", ["document_id", "section_number"], unique=False)
    op.create_index("ix_specification_sections_organization_id", "specification_sections", ["organization_id"], unique=False)

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
            for key, module, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in _PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")
    op.drop_table("specification_sections")
    op.drop_table("document_revisions")
    op.drop_table("documents")
    op.drop_table("document_folders")
