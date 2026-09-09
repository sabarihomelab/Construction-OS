from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class DevicePlatform(StrEnum):
    WEB = "web"
    PWA = "pwa"
    IOS = "ios"
    ANDROID = "android"
    DESKTOP = "desktop"


class SyncMutationOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTION = "action"


class SyncMutationStatus(StrEnum):
    RECEIVED = "received"
    APPLIED = "applied"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class SyncConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ClientDevice(UUIDTimestampMixin, Base):
    __tablename__ = "client_devices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "installation_id",
            name="uq_client_devices_org_user_installation",
        ),
        UniqueConstraint("id", "organization_id", name="uq_client_devices_id_org"),
        Index("ix_client_devices_org_user", "organization_id", "user_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    installation_id: Mapped[str] = mapped_column(String(128))
    platform: Mapped[DevicePlatform] = mapped_column(
        Enum(DevicePlatform, native_enum=False, values_callable=enum_values)
    )
    device_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)


class DeviceSyncState(Base):
    __tablename__ = "device_sync_state"
    __table_args__ = (
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["client_devices.id", "client_devices.organization_id"],
            name="fk_device_sync_state_device_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "last_acknowledged_event_sequence >= 0",
            name="ck_device_sync_state_ack_sequence",
        ),
        CheckConstraint("revision >= 1", name="ck_device_sync_state_revision"),
    )

    device_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    last_acknowledged_event_sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    last_sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SyncMutationReceipt(UUIDTimestampMixin, Base):
    __tablename__ = "sync_mutation_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["client_devices.id", "client_devices.organization_id"],
            name="fk_sync_mutation_receipts_device_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "device_id",
            "client_mutation_id",
            name="uq_sync_mutation_receipts_client_mutation",
        ),
        UniqueConstraint("id", "organization_id", name="uq_sync_mutation_receipts_id_org"),
        CheckConstraint("length(request_hash) = 64", name="ck_sync_mutation_receipts_hash_length"),
        CheckConstraint(
            "base_version IS NULL OR base_version >= 1",
            name="ck_sync_mutation_receipts_base_version",
        ),
        CheckConstraint(
            "server_version IS NULL OR server_version >= 1",
            name="ck_sync_mutation_receipts_server_version",
        ),
        Index("ix_sync_mutation_receipts_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    device_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    client_mutation_id: Mapped[UUID] = mapped_column(Uuid)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    operation: Mapped[SyncMutationOperation] = mapped_column(
        Enum(SyncMutationOperation, native_enum=False, values_callable=enum_values)
    )
    base_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[SyncMutationStatus] = mapped_column(
        Enum(SyncMutationStatus, native_enum=False, values_callable=enum_values),
        default=SyncMutationStatus.RECEIVED,
    )
    server_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncConflict(UUIDTimestampMixin, Base):
    __tablename__ = "sync_conflicts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["client_devices.id", "client_devices.organization_id"],
            name="fk_sync_conflicts_device_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["mutation_receipt_id", "organization_id"],
            ["sync_mutation_receipts.id", "sync_mutation_receipts.organization_id"],
            name="fk_sync_conflicts_receipt_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("mutation_receipt_id", name="uq_sync_conflicts_mutation_receipt"),
        CheckConstraint("base_version >= 1", name="ck_sync_conflicts_base_version"),
        CheckConstraint("server_version >= 1", name="ck_sync_conflicts_server_version"),
        Index("ix_sync_conflicts_org_status", "organization_id", "status"),
        Index("ix_sync_conflicts_org_entity", "organization_id", "entity_type", "entity_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    device_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    mutation_receipt_id: Mapped[UUID] = mapped_column(Uuid)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(160))
    base_version: Mapped[int] = mapped_column(BigInteger)
    server_version: Mapped[int] = mapped_column(BigInteger)
    client_patch: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    server_values: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[SyncConflictStatus] = mapped_column(
        Enum(SyncConflictStatus, native_enum=False, values_callable=enum_values),
        default=SyncConflictStatus.OPEN,
    )
    resolution: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
