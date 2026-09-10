from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class HealthState(StrEnum):
    HEALTHY = "healthy"
    ATTENTION = "attention"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class OperationalEventStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class OperationalHealthSnapshot(UUIDTimestampMixin, Base):
    __tablename__ = "operational_health_snapshots"
    __table_args__ = (
        Index(
            "ix_operational_health_snapshots_org_component_time",
            "organization_id",
            "category",
            "component_key",
            "observed_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(80), index=True)
    component_key: Mapped[str] = mapped_column(String(140), index=True)
    state: Mapped[HealthState] = mapped_column(
        Enum(HealthState, native_enum=False, values_callable=enum_values)
    )
    summary: Mapped[str] = mapped_column(String(255))
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationalEvent(UUIDTimestampMixin, Base):
    __tablename__ = "operational_events"
    __table_args__ = (
        Index("ix_operational_events_org_status", "organization_id", "status", "severity"),
        Index("ix_operational_events_org_key", "organization_id", "event_key", "last_seen_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    event_key: Mapped[str] = mapped_column(String(180), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[HealthState] = mapped_column(
        Enum(HealthState, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[OperationalEventStatus] = mapped_column(
        Enum(OperationalEventStatus, native_enum=False, values_callable=enum_values),
        default=OperationalEventStatus.OPEN,
    )
    title: Mapped[str] = mapped_column(String(180))
    summary: Mapped[str] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(String(140))
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(BigInteger, default=1)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)


class OperationsRetentionPolicy(UUIDTimestampMixin, Base):
    __tablename__ = "operations_retention_policies"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(80), index=True)
    snapshot_days: Mapped[int] = mapped_column(Integer, default=90)
    event_days: Mapped[int] = mapped_column(Integer, default=365)
