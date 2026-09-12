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
    op.add_column("upload_sessions", sa.Column("client_upload_id", sa.Uuid(), nullable=True))
    op.add_column("upload_sessions", sa.Column("context_type", sa.String(length=80), nullable=True))
    op.add_column("upload_sessions", sa.Column("context_id", sa.Uuid(), nullable=True))
    op.add_column("upload_sessions", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "upload_sessions",
        sa.Column("chunk_size_bytes", sa.Integer(), nullable=False, server_default="5242880"),
    )
    op.add_column(
        "upload_sessions",
        sa.Column("uploaded_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "upload_sessions",
        sa.Column("deduplicated_storage_object_id", sa.Uuid(), nullable=True),
    )
    op.add_column("upload_sessions", sa.Column("finalized_asset_id", sa.Uuid(), nullable=True))
    op.add_column("upload_sessions", sa.Column("finalized_version", sa.Integer(), nullable=True))
    op.add_column(
        "upload_sessions",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_unique_constraint(
        "uq_upload_sessions_org_client_upload",
        "upload_sessions",
        ["organization_id", "client_upload_id"],
    )
    op.create_index(
        "ix_upload_sessions_org_context",
        "upload_sessions",
        ["organization_id", "context_type", "context_id"],
    )
    op.create_index(
        "ix_upload_sessions_dedup_object",
        "upload_sessions",
        ["deduplicated_storage_object_id"],
    )
    op.create_check_constraint(
        "ck_upload_sessions_chunk_size_positive",
        "upload_sessions",
        "chunk_size_bytes > 0",
    )
    op.create_check_constraint(
        "ck_upload_sessions_uploaded_bytes_nonnegative",
        "upload_sessions",
        "uploaded_bytes >= 0",
    )
    op.create_check_constraint(
        "ck_upload_sessions_request_hash_length",
        "upload_sessions",
        "request_hash IS NULL OR length(request_hash) = 64",
    )
    op.create_check_constraint(
        "ck_upload_sessions_finalized_version_positive",
        "upload_sessions",
        "finalized_version IS NULL OR finalized_version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_upload_sessions_finalized_version_positive",
        "upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_upload_sessions_request_hash_length",
        "upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_upload_sessions_uploaded_bytes_nonnegative",
        "upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_upload_sessions_chunk_size_positive",
        "upload_sessions",
        type_="check",
    )
    op.drop_index("ix_upload_sessions_dedup_object", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_org_context", table_name="upload_sessions")
    op.drop_constraint(
        "uq_upload_sessions_org_client_upload",
        "upload_sessions",
        type_="unique",
    )
    op.drop_column("upload_sessions", "cancelled_at")
    op.drop_column("upload_sessions", "finalized_version")
    op.drop_column("upload_sessions", "finalized_asset_id")
    op.drop_column("upload_sessions", "deduplicated_storage_object_id")
    op.drop_column("upload_sessions", "uploaded_bytes")
    op.drop_column("upload_sessions", "chunk_size_bytes")
    op.drop_column("upload_sessions", "request_hash")
    op.drop_column("upload_sessions", "context_id")
    op.drop_column("upload_sessions", "context_type")
    op.drop_column("upload_sessions", "client_upload_id")
