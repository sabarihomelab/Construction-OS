from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
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


class MappingVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class IntegrationConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class MappingProfile(UUIDTimestampMixin, Base):
    __tablename__ = "mapping_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_mapping_profiles_connector_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "connector_id", "key", name="uq_mapping_profiles_connector_key"),
        UniqueConstraint("id", "organization_id", name="uq_mapping_profiles_id_org"),
        CheckConstraint("current_version >= 0", name="ck_mapping_profiles_current_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    connector_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    key: Mapped[str] = mapped_column(String(140))
    source_type: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(String(120))
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)


class MappingProfileVersion(UUIDTimestampMixin, Base):
    __tablename__ = "mapping_profile_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["profile_id", "organization_id"],
            ["mapping_profiles.id", "mapping_profiles.organization_id"],
            name="fk_mapping_profile_versions_profile_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("profile_id", "version", name="uq_mapping_profile_versions_version"),
        UniqueConstraint("id", "organization_id", name="uq_mapping_profile_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_mapping_profile_versions_version"),
        Index("ix_mapping_profile_versions_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[MappingVersionStatus] = mapped_column(
        Enum(MappingVersionStatus, native_enum=False, values_callable=enum_values),
        default=MappingVersionStatus.DRAFT,
    )
    mapping_spec: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class SyncCheckpoint(UUIDTimestampMixin, Base):
    __tablename__ = "sync_checkpoints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_sync_checkpoints_connector_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "connector_id", "stream_key", name="uq_sync_checkpoints_stream"),
        CheckConstraint("revision >= 1", name="ck_sync_checkpoints_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    connector_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    stream_key: Mapped[str] = mapped_column(String(160))
    cursor: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    advanced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationConflict(UUIDTimestampMixin, Base):
    __tablename__ = "integration_conflicts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connector_id", "organization_id"],
            ["integration_connectors.id", "integration_connectors.organization_id"],
            name="fk_integration_conflicts_connector_org",
            ondelete="CASCADE",
        ),
        Index("ix_integration_conflicts_org_status", "organization_id", "status"),
        Index("ix_integration_conflicts_source", "connector_id", "external_type", "external_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    connector_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    external_type: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str] = mapped_column(String(255))
    internal_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    internal_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[IntegrationConflictStatus] = mapped_column(
        Enum(IntegrationConflictStatus, native_enum=False, values_callable=enum_values),
        default=IntegrationConflictStatus.OPEN,
    )
    reason_code: Mapped[str] = mapped_column(String(120))
    source_values: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    internal_values: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    resolution: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
