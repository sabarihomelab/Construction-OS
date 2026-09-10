from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ExportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ExportScopeType(StrEnum):
    COMPANY = "company"
    PROJECT = "project"
    MODULE = "module"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class DataExportRequest(UUIDTimestampMixin, Base):
    __tablename__ = "data_export_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["output_file_asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_data_export_requests_output_asset_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_data_export_requests_id_org"),
        CheckConstraint("manifest_version >= 1", name="ck_data_export_requests_manifest_version"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_data_export_requests_progress"),
        Index("ix_data_export_requests_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    scope_type: Mapped[ExportScopeType] = mapped_column(
        Enum(ExportScopeType, native_enum=False, values_callable=enum_values)
    )
    scope_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, native_enum=False, values_callable=enum_values),
        default=ExportStatus.QUEUED,
    )
    include_files: Mapped[bool] = mapped_column(Boolean, default=True)
    include_audit: Mapped[bool] = mapped_column(Boolean, default=False)
    manifest_version: Mapped[int] = mapped_column(Integer, default=1)
    options: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    output_file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataExportManifestItem(UUIDTimestampMixin, Base):
    __tablename__ = "data_export_manifest_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["export_request_id", "organization_id"],
            ["data_export_requests.id", "data_export_requests.organization_id"],
            name="fk_data_export_manifest_items_request_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "export_request_id", "relative_path", name="uq_data_export_manifest_items_path"
        ),
        CheckConstraint("record_count >= 0", name="ck_data_export_manifest_items_records"),
        CheckConstraint("file_count >= 0", name="ck_data_export_manifest_items_files"),
        CheckConstraint("schema_version >= 1", name="ck_data_export_manifest_items_schema_version"),
        CheckConstraint(
            "checksum_sha256 IS NULL OR length(checksum_sha256) = 64",
            name="ck_data_export_manifest_items_checksum",
        ),
        Index("ix_data_export_manifest_items_export_module", "export_request_id", "module_key"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    export_request_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    module_key: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    relative_path: Mapped[str] = mapped_column(String(512))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    record_count: Mapped[int] = mapped_column(BigInteger, default=0)
    file_count: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
