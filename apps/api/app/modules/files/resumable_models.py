from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ResumableUploadState(UUIDTimestampMixin, Base):
    __tablename__ = "resumable_upload_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deduplicated_storage_object_id", "organization_id"],
            ["storage_objects.id", "storage_objects.organization_id"],
            name="fk_resumable_upload_state_dedup_object_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "client_upload_id",
            name="uq_resumable_upload_state_org_client",
        ),
        CheckConstraint(
            "chunk_size_bytes > 0",
            name="ck_resumable_upload_state_chunk_size_positive",
        ),
        CheckConstraint(
            "uploaded_bytes >= 0",
            name="ck_resumable_upload_state_uploaded_nonnegative",
        ),
        CheckConstraint(
            "length(request_hash) = 64",
            name="ck_resumable_upload_state_request_hash_length",
        ),
        CheckConstraint(
            "finalized_version IS NULL OR finalized_version >= 1",
            name="ck_resumable_upload_state_finalized_version_positive",
        ),
        Index(
            "ix_resumable_upload_state_org_context",
            "organization_id",
            "context_type",
            "context_id",
        ),
        Index(
            "ix_resumable_upload_state_dedup_object",
            "deduplicated_storage_object_id",
        ),
    )

    upload_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    client_upload_id: Mapped[UUID] = mapped_column(Uuid)
    context_type: Mapped[str] = mapped_column(String(80))
    context_id: Mapped[UUID] = mapped_column(Uuid)
    request_hash: Mapped[str] = mapped_column(String(64))
    chunk_size_bytes: Mapped[int] = mapped_column(Integer, default=5 * 1024 * 1024)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    deduplicated_storage_object_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    finalized_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    finalized_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
