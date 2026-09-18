from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin
from app.modules.notifications.models import DigestFrequency, NotificationChannel, enum_values


class NotificationDigestStatus(StrEnum):
    QUEUED = "queued"
    BUILDING = "building"
    READY = "ready"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationDigest(UUIDTimestampMixin, Base):
    __tablename__ = "notification_digests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_digests_membership_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_notification_digests_id_org"),
        UniqueConstraint(
            "organization_id",
            "membership_id",
            "channel",
            "frequency",
            "window_start",
            "window_end",
            name="uq_notification_digests_delivery_window",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_notification_digests_attempt_count"),
        CheckConstraint("window_end > window_start", name="ck_notification_digests_window"),
        Index("ix_notification_digests_queue", "status", "scheduled_at", "created_at"),
        Index("ix_notification_digests_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, values_callable=enum_values)
    )
    frequency: Mapped[DigestFrequency] = mapped_column(
        Enum(DigestFrequency, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[NotificationDigestStatus] = mapped_column(
        Enum(NotificationDigestStatus, native_enum=False, values_callable=enum_values),
        default=NotificationDigestStatus.QUEUED,
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    provider_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationDigestItem(Base):
    __tablename__ = "notification_digest_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["digest_id", "organization_id"],
            ["notification_digests.id", "notification_digests.organization_id"],
            name="fk_notification_digest_items_digest_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["notification_id", "organization_id"],
            ["notifications.id", "notifications.organization_id"],
            name="fk_notification_digest_items_notification_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("digest_id", "notification_id", name="uq_notification_digest_items_pair"),
    )

    digest_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    notification_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
