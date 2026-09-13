from datetime import datetime, time
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
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
    Time,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class NotificationCategory(StrEnum):
    CRITICAL = "critical"
    ACTION_REQUIRED = "action_required"
    APPROVAL = "approval"
    ASSIGNED = "assigned"
    PROJECT_UPDATE = "project_update"
    FYI = "fyi"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"


class NotificationDeliveryMode(StrEnum):
    IMMEDIATE = "immediate"
    DIGEST = "digest"
    OFF = "off"


class DigestFrequency(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class NotificationDeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Notification(UUIDTimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["recipient_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notifications_recipient_membership_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_notifications_id_org"),
        UniqueConstraint(
            "organization_id",
            "recipient_membership_id",
            "dedupe_key",
            name="uq_notifications_recipient_dedupe",
        ),
        Index(
            "ix_notifications_recipient_unread",
            "organization_id",
            "recipient_membership_id",
            "read_at",
            "created_at",
        ),
        Index("ix_notifications_org_entity", "organization_id", "entity_type", "entity_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    recipient_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[NotificationCategory] = mapped_column(
        Enum(NotificationCategory, native_enum=False, values_callable=enum_values), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(120))
    reason_text: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    template_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    template_variables: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    required_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True, index=True
    )
    scope_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class NotificationPreference(UUIDTimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_preferences_membership_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "membership_id",
            "event_type",
            "channel",
            name="uq_notification_preferences_event_channel",
        ),
        Index("ix_notification_preferences_org_member", "organization_id", "membership_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(160), default="*")
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, values_callable=enum_values)
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_mode: Mapped[NotificationDeliveryMode] = mapped_column(
        Enum(NotificationDeliveryMode, native_enum=False, values_callable=enum_values),
        default=NotificationDeliveryMode.IMMEDIATE,
    )
    digest_frequency: Mapped[DigestFrequency | None] = mapped_column(
        Enum(DigestFrequency, native_enum=False, values_callable=enum_values), nullable=True
    )


class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_settings_membership_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(quiet_hours_enabled = false) OR (quiet_start IS NOT NULL AND quiet_end IS NOT NULL)",
            name="ck_notification_settings_quiet_hours",
        ),
    )

    membership_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    digest_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificationSubscription(UUIDTimestampMixin, Base):
    __tablename__ = "notification_subscriptions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_subscriptions_membership_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "membership_id",
            "topic_type",
            "topic_id",
            "event_type",
            name="uq_notification_subscriptions_topic_event",
        ),
        Index(
            "ix_notification_subscriptions_topic",
            "organization_id",
            "topic_type",
            "topic_id",
            "enabled",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    topic_type: Mapped[str] = mapped_column(String(80))
    topic_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(160), default="*")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationDelivery(UUIDTimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["notification_id", "organization_id"],
            ["notifications.id", "notifications.organization_id"],
            name="fk_notification_deliveries_notification_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "notification_id", "channel", name="uq_notification_deliveries_notification_channel"
        ),
        CheckConstraint("attempt_count >= 0", name="ck_notification_deliveries_attempt_count"),
        Index(
            "ix_notification_deliveries_queue",
            "status",
            "scheduled_at",
            "created_at",
        ),
        Index("ix_notification_deliveries_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    notification_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[NotificationDeliveryStatus] = mapped_column(
        Enum(NotificationDeliveryStatus, native_enum=False, values_callable=enum_values),
        default=NotificationDeliveryStatus.QUEUED,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    provider_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
