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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class StorageObjectKind(StrEnum):
    ORIGINAL = "original"
    DERIVATIVE = "derivative"
    TEMPORARY = "temporary"


class StorageObjectStatus(StrEnum):
    ACTIVE = "active"
    PENDING_DELETE = "pending_delete"
    DELETED = "deleted"


class FileAssetStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"
    DELETED = "deleted"


class FileScanStatus(StrEnum):
    PENDING = "pending"
    SCANNING = "scanning"
    CLEAN = "clean"
    QUARANTINED = "quarantined"
    FAILED = "failed"


class FileProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class FileSourceType(StrEnum):
    USER = "user"
    INTEGRATION = "integration"
    IMPORT = "import"
    SYSTEM = "system"


class UploadStatus(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FINALIZED = "finalized"
    EXPIRED = "expired"
    FAILED = "failed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class StorageObject(UUIDTimestampMixin, Base):
    __tablename__ = "storage_objects"
    __table_args__ = (
        UniqueConstraint("provider_key", "storage_key", name="uq_storage_objects_provider_key"),
        UniqueConstraint(
            "organization_id",
            "sha256",
            "size_bytes",
            name="uq_storage_objects_org_hash_size",
        ),
        CheckConstraint("size_bytes > 0", name="ck_storage_objects_size_positive"),
        CheckConstraint("length(sha256) = 64", name="ck_storage_objects_sha256_length"),
        Index("ix_storage_objects_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    provider_key: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512))
    kind: Mapped[StorageObjectKind] = mapped_column(
        Enum(StorageObjectKind, native_enum=False, values_callable=enum_values)
    )
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[StorageObjectStatus] = mapped_column(
        Enum(StorageObjectStatus, native_enum=False, values_callable=enum_values),
        default=StorageObjectStatus.ACTIVE,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrganizationStorageUsage(Base):
    __tablename__ = "organization_storage_usage"
    __table_args__ = (
        CheckConstraint("committed_bytes >= 0", name="ck_storage_usage_committed_nonnegative"),
        CheckConstraint("reserved_bytes >= 0", name="ck_storage_usage_reserved_nonnegative"),
        CheckConstraint("object_count >= 0", name="ck_storage_usage_object_count_nonnegative"),
        CheckConstraint("revision >= 1", name="ck_storage_usage_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    committed_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    object_count: Mapped[int] = mapped_column(BigInteger, default=0)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FileAsset(UUIDTimestampMixin, Base):
    __tablename__ = "file_assets"
    __table_args__ = (
        CheckConstraint("current_version >= 1", name="ck_file_assets_current_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FileAssetStatus] = mapped_column(
        Enum(FileAssetStatus, native_enum=False, values_callable=enum_values),
        default=FileAssetStatus.ACTIVE,
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FileVersion(UUIDTimestampMixin, Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint("asset_id", "version", name="uq_file_versions_asset_version"),
        CheckConstraint("version >= 1", name="ck_file_versions_version"),
        CheckConstraint("size_bytes > 0", name="ck_file_versions_size_positive"),
        CheckConstraint("length(sha256) = 64", name="ck_file_versions_sha256_length"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_assets.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    storage_object_id: Mapped[UUID] = mapped_column(
        ForeignKey("storage_objects.id", ondelete="RESTRICT"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    declared_content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    detected_content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    scan_status: Mapped[FileScanStatus] = mapped_column(
        Enum(FileScanStatus, native_enum=False, values_callable=enum_values),
        default=FileScanStatus.PENDING,
    )
    processing_status: Mapped[FileProcessingStatus] = mapped_column(
        Enum(FileProcessingStatus, native_enum=False, values_callable=enum_values),
        default=FileProcessingStatus.PENDING,
    )
    source_type: Mapped[FileSourceType] = mapped_column(
        Enum(FileSourceType, native_enum=False, values_callable=enum_values)
    )
    source_system: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FileLink(UUIDTimestampMixin, Base):
    __tablename__ = "file_links"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            "asset_id",
            "relation_type",
            name="uq_file_links_entity_asset_relation",
        ),
        CheckConstraint(
            "pinned_version IS NULL OR pinned_version >= 1",
            name="ck_file_links_pinned_version",
        ),
        Index("ix_file_links_org_entity", "organization_id", "entity_type", "entity_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_assets.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(80), default="attachment")
    pinned_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FileVariant(UUIDTimestampMixin, Base):
    __tablename__ = "file_variants"
    __table_args__ = (
        UniqueConstraint("file_version_id", "variant_key", name="uq_file_variants_version_key"),
        CheckConstraint("width IS NULL OR width > 0", name="ck_file_variants_width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="ck_file_variants_height_positive"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    file_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_versions.id", ondelete="CASCADE"), index=True
    )
    variant_key: Mapped[str] = mapped_column(String(64))
    storage_object_id: Mapped[UUID] = mapped_column(
        ForeignKey("storage_objects.id", ondelete="RESTRICT"), index=True
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)


class UploadSession(UUIDTimestampMixin, Base):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        CheckConstraint(
            "expected_size_bytes IS NULL OR expected_size_bytes > 0",
            name="ck_upload_sessions_expected_size_positive",
        ),
        CheckConstraint(
            "reserved_bytes >= 0",
            name="ck_upload_sessions_reserved_bytes_nonnegative",
        ),
        Index("ix_upload_sessions_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_key: Mapped[str] = mapped_column(String(64))
    temporary_storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    declared_content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    expected_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, native_enum=False, values_callable=enum_values),
        default=UploadStatus.CREATED,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
