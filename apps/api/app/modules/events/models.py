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
    Identity,
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


class OutboxEventStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class OutboxEvent(UUIDTimestampMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recipient_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_outbox_events_recipient_membership_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("sequence", name="uq_outbox_events_sequence"),
        CheckConstraint("event_schema_version >= 1", name="ck_outbox_events_schema_version"),
        CheckConstraint("publish_attempts >= 0", name="ck_outbox_events_publish_attempts"),
        CheckConstraint(
            "entity_version IS NULL OR entity_version >= 1",
            name="ck_outbox_events_entity_version",
        ),
        CheckConstraint(
            "(scope_type IS NULL AND scope_id IS NULL) OR "
            "(scope_type IS NOT NULL AND scope_id IS NOT NULL)",
            name="ck_outbox_events_scope_pair",
        ),
        Index("ix_outbox_events_org_sequence", "organization_id", "sequence"),
        Index("ix_outbox_events_status_available", "status", "available_at"),
        Index(
            "ix_outbox_events_recipient_sequence",
            "organization_id",
            "recipient_membership_id",
            "sequence",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    recipient_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    event_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    entity_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    required_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True, index=True
    )
    scope_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    correlation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[OutboxEventStatus] = mapped_column(
        Enum(OutboxEventStatus, native_enum=False, values_callable=enum_values),
        default=OutboxEventStatus.PENDING,
        index=True,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
