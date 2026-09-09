from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    INTEGRATION = "integration"
    SUPPORT = "support"


class AuditRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_occurred", "organization_id", "occurred_at"),
        Index("ix_audit_events_target", "organization_id", "target_type", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_type: Mapped[AuditActorType] = mapped_column(
        Enum(AuditActorType, native_enum=False, values_callable=enum_values)
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(180), index=True)
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    risk: Mapped[AuditRisk] = mapped_column(
        Enum(AuditRisk, native_enum=False, values_callable=enum_values), default=AuditRisk.LOW
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    metadata: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
