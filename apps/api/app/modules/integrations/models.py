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


class ConnectorStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    AUTH_REQUIRED = "auth_required"


class IngestionStatus(StrEnum):
    RECEIVED = "received"
    VALIDATING = "validating"
    STAGED = "staged"
    PROCESSING = "processing"
    READY_TO_COMMIT = "ready_to_commit"
    COMMITTED = "committed"
    QUARANTINED = "quarantined"
    RETRYING = "retrying"
    FAILED = "failed"


class StagedRecordStatus(StrEnum):
    STAGED = "staged"
    VALID = "valid"
    INVALID = "invalid"
    MAPPED = "mapped"
    COMMITTED = "committed"
    QUARANTINED = "quarantined"


class ReconciliationStatus(StrEnum):
    CURRENT = "current"
    CHANGED = "changed"
    CONFLICT = "conflict"
    MISSING_SOURCE = "missing_source"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class IntegrationConnector(UUIDTimestampMixin, Base):
    __tablename__ = "integration_connectors"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_integration_connectors_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_integration_connectors_id_org"),
        Index("ix_integration_connectors_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120))
    provider_type: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(180))
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus, native_enum=False, values_callable=enum_values),
        default=ConnectorStatus.ACTIVE,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    credential_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)


class IngestionBatch(UUIDTimestampMixin, Base):
    __tablename__ = "ingestion_batches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_ingestion_batches_connector_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "connector_id", "idempotency_key", name="uq_ingestion_batches_idempotency"
        ),
        UniqueConstraint("id", "organization_id", name="uq_ingestion_batches_id_org"),
        CheckConstraint("received_count >= 0", name="ck_ingestion_batches_received_count"),
        CheckConstraint("valid_count >= 0", name="ck_ingestion_batches_valid_count"),
        CheckConstraint("invalid_count >= 0", name="ck_ingestion_batches_invalid_count"),
        CheckConstraint("committed_count >= 0", name="ck_ingestion_batches_committed_count"),
        Index("ix_ingestion_batches_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    connector_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    external_batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, native_enum=False, values_callable=enum_values),
        default=IngestionStatus.RECEIVED,
    )
    mapping_version: Mapped[int] = mapped_column(Integer, default=1)
    received_count: Mapped[int] = mapped_column(BigInteger, default=0)
    valid_count: Mapped[int] = mapped_column(BigInteger, default=0)
    invalid_count: Mapped[int] = mapped_column(BigInteger, default=0)
    committed_count: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class StagedExternalRecord(UUIDTimestampMixin, Base):
    __tablename__ = "staged_external_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "organization_id"],
            ["ingestion_batches.id", "ingestion_batches.organization_id"],
            name="fk_staged_external_records_batch_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("batch_id", "external_type", "external_id", name="uq_staged_external_records_identity"),
        CheckConstraint("length(payload_checksum) = 64", name="ck_staged_external_records_checksum"),
        Index("ix_staged_external_records_batch_status", "batch_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    batch_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    external_type: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_checksum: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[StagedRecordStatus] = mapped_column(
        Enum(StagedRecordStatus, native_enum=False, values_callable=enum_values),
        default=StagedRecordStatus.STAGED,
    )
    mapping_errors: Mapped[list[object]] = mapped_column(JSONB, default=list)
    canonical_entity_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    canonical_entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class ExternalRecordMapping(UUIDTimestampMixin, Base):
    __tablename__ = "external_record_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_external_record_mappings_connector_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id", "connector_id", "external_type", "external_id", name="uq_external_record_mappings_source"
        ),
        CheckConstraint("length(source_checksum) = 64", name="ck_external_record_mappings_checksum"),
        Index("ix_external_record_mappings_internal", "organization_id", "internal_type", "internal_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    connector_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    external_type: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_checksum: Mapped[str] = mapped_column(String(64))
    mapping_version: Mapped[int] = mapped_column(Integer, default=1)
    internal_type: Mapped[str] = mapped_column(String(120))
    internal_id: Mapped[str] = mapped_column(String(160))
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, native_enum=False, values_callable=enum_values),
        default=ReconciliationStatus.CURRENT,
    )
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
