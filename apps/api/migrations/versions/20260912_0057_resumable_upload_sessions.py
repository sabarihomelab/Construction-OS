"""Add resumable/idempotent upload session state.

Revision ID: 20260912_0057
Revises: 20260912_0056
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0057"
down_revision: str | None = "20260912_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resumable_upload_states",
        sa.Column("upload_session_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("client_upload_id", sa.Uuid(), nullable=False),
        sa.Column("context_type", sa.String(length=80), nullable=False),
        sa.Column("context_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_size_bytes", sa.Integer(), nullable=False, server_default="5242880"),
        sa.Column("uploaded_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("deduplicated_storage_object_id", sa.Uuid(), nullable=True),
        sa.Column("finalized_asset_id", sa.Uuid(), nullable=True),
        sa.Column("finalized_version", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["upload_session_id"],
            ["upload_sessions.id"],
            name="fk_resumable_upload_state_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_resumable_upload_state_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deduplicated_storage_object_id", "organization_id"],
            ["storage_objects.id", "storage_objects.organization_id"],
            name="fk_resumable_upload_state_dedup_object_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("upload_session_id"),
        sa.UniqueConstraint(
            "organization_id",
            "client_upload_id",
            name="uq_resumable_upload_state_org_client",
        ),
        sa.CheckConstraint(
            "chunk_size_bytes > 0",
            name="ck_resumable_upload_state_chunk_size_positive",
        ),
        sa.CheckConstraint(
            "uploaded_bytes >= 0",
            name="ck_resumable_upload_state_uploaded_nonnegative",
        ),
        sa.CheckConstraint(
            "length(request_hash) = 64",
            name="ck_resumable_upload_state_request_hash_length",
        ),
        sa.CheckConstraint(
            "finalized_version IS NULL OR finalized_version >= 1",
            name="ck_resumable_upload_state_finalized_version_positive",
        ),
    )
    op.create_index(
        "ix_resumable_upload_state_org_context",
        "resumable_upload_states",
        ["organization_id", "context_type", "context_id"],
    )
    op.create_index(
        "ix_resumable_upload_state_dedup_object",
        "resumable_upload_states",
        ["deduplicated_storage_object_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resumable_upload_state_dedup_object",
        table_name="resumable_upload_states",
    )
    op.drop_index(
        "ix_resumable_upload_state_org_context",
        table_name="resumable_upload_states",
    )
    op.drop_table("resumable_upload_states")
