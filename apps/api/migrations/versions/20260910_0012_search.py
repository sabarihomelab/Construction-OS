"""Create tenant-scoped search projection foundation.

Revision ID: 20260910_0012
Revises: 20260910_0011
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0012"
down_revision: str | None = "20260910_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_documents",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=False),
        sa.Column("entity_version", sa.BigInteger(), nullable=True),
        sa.Column("required_permission_key", sa.String(length=160), nullable=True),
        sa.Column("scope_type", sa.String(length=40), nullable=True),
        sa.Column("scope_id", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("subtitle", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("route_hint", sa.String(length=500), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(subtitle, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(keywords_text, '')), 'B') || "
                "setweight(to_tsvector('simple', coalesce(body, '')), 'C')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "entity_version IS NULL OR entity_version >= 1",
            name="ck_search_documents_entity_version",
        ),
        sa.CheckConstraint(
            "(scope_type IS NULL AND scope_id IS NULL) OR "
            "(scope_type IS NOT NULL AND scope_id IS NOT NULL)",
            name="ck_search_documents_scope_pair",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_search_documents_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["required_permission_key"],
            ["permissions.key"],
            name=op.f("fk_search_documents_required_permission_key_permissions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_documents")),
        sa.UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            name="uq_search_documents_org_entity",
        ),
    )
    op.create_index(op.f("ix_search_documents_organization_id"), "search_documents", ["organization_id"])
    op.create_index(op.f("ix_search_documents_entity_type"), "search_documents", ["entity_type"])
    op.create_index(op.f("ix_search_documents_entity_id"), "search_documents", ["entity_id"])
    op.create_index(op.f("ix_search_documents_required_permission_key"), "search_documents", ["required_permission_key"])
    op.create_index("ix_search_documents_org_type", "search_documents", ["organization_id", "entity_type"])
    op.create_index("ix_search_documents_org_scope", "search_documents", ["organization_id", "scope_type", "scope_id"])
    op.create_index("ix_search_documents_vector", "search_documents", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_search_documents_vector", table_name="search_documents")
    op.drop_index("ix_search_documents_org_scope", table_name="search_documents")
    op.drop_index("ix_search_documents_org_type", table_name="search_documents")
    op.drop_index(op.f("ix_search_documents_required_permission_key"), table_name="search_documents")
    op.drop_index(op.f("ix_search_documents_entity_id"), table_name="search_documents")
    op.drop_index(op.f("ix_search_documents_entity_type"), table_name="search_documents")
    op.drop_index(op.f("ix_search_documents_organization_id"), table_name="search_documents")
    op.drop_table("search_documents")
