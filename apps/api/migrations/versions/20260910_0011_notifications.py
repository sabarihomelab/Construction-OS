"""Create notification, preference, and digest foundation.

Revision ID: 20260910_0011
Revises: 20260910_0010
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0011"
down_revision: str | None = "20260910_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_organization_memberships_id_org",
        "organization_memberships",
        ["id", "organization_id"],
    )

    op.add_column("outbox_events", sa.Column("recipient_membership_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_outbox_events_recipient_membership_org",
        "outbox_events",
        "organization_memberships",
        ["recipient_membership_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_outbox_events_recipient_membership_id"),
        "outbox_events",
        ["recipient_membership_id"],
    )
    op.create_index(
        "ix_outbox_events_recipient_sequence",
        "outbox_events",
        ["organization_id", "recipient_membership_id", "sequence"],
    )

    op.create_table(
        "notifications",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_membership_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "critical",
                "action_required",
                "approval",
                "assigned",
                "project_update",
                "fyi",
                name="notificationcategory",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column("reason_text", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("template_key", sa.String(length=160), nullable=True),
        sa.Column("template_variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("required_permission_key", sa.String(length=160), nullable=True),
        sa.Column("scope_type", sa.String(length=40), nullable=True),
        sa.Column("scope_id", sa.String(length=160), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("dedupe_key", sa.String(length=180), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["recipient_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notifications_recipient_membership_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["required_permission_key"], ["permissions.key"], ondelete="RESTRICT",
            name=op.f("fk_notifications_required_permission_key_permissions")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL",
            name=op.f("fk_notifications_created_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("id", "organization_id", name="uq_notifications_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "recipient_membership_id",
            "dedupe_key",
            name="uq_notifications_recipient_dedupe",
        ),
    )
    op.create_index(op.f("ix_notifications_organization_id"), "notifications", ["organization_id"])
    op.create_index(op.f("ix_notifications_recipient_membership_id"), "notifications", ["recipient_membership_id"])
    op.create_index(op.f("ix_notifications_event_type"), "notifications", ["event_type"])
    op.create_index(op.f("ix_notifications_category"), "notifications", ["category"])
    op.create_index(op.f("ix_notifications_required_permission_key"), "notifications", ["required_permission_key"])
    op.create_index(op.f("ix_notifications_entity_type"), "notifications", ["entity_type"])
    op.create_index(op.f("ix_notifications_entity_id"), "notifications", ["entity_id"])
    op.create_index(
        "ix_notifications_recipient_unread",
        "notifications",
        ["organization_id", "recipient_membership_id", "read_at", "created_at"],
    )
    op.create_index(
        "ix_notifications_org_entity",
        "notifications",
        ["organization_id", "entity_type", "entity_id"],
    )

    op.create_table(
        "notification_preferences",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False, server_default="*"),
        sa.Column(
            "channel",
            sa.Enum("in_app", "email", "push", name="notificationchannel", native_enum=False),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "delivery_mode",
            sa.Enum("immediate", "digest", "off", name="notificationdeliverymode", native_enum=False),
            nullable=False,
            server_default="immediate",
        ),
        sa.Column(
            "digest_frequency",
            sa.Enum("hourly", "daily", "weekly", name="digestfrequency", native_enum=False),
            nullable=True,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_preferences_membership_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
        sa.UniqueConstraint(
            "organization_id",
            "membership_id",
            "event_type",
            "channel",
            name="uq_notification_preferences_event_channel",
        ),
    )
    op.create_index(op.f("ix_notification_preferences_organization_id"), "notification_preferences", ["organization_id"])
    op.create_index(op.f("ix_notification_preferences_membership_id"), "notification_preferences", ["membership_id"])
    op.create_index("ix_notification_preferences_org_member", "notification_preferences", ["organization_id", "membership_id"])

    op.create_table(
        "notification_settings",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quiet_start", sa.Time(), nullable=True),
        sa.Column("quiet_end", sa.Time(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("digest_time", sa.Time(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "(quiet_hours_enabled = false) OR (quiet_start IS NOT NULL AND quiet_end IS NOT NULL)",
            name="ck_notification_settings_quiet_hours",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_settings_membership_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("membership_id", name=op.f("pk_notification_settings")),
    )
    op.create_index(op.f("ix_notification_settings_organization_id"), "notification_settings", ["organization_id"])

    op.create_table(
        "notification_subscriptions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("topic_type", sa.String(length=80), nullable=False),
        sa.Column("topic_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False, server_default="*"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_subscriptions_membership_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_subscriptions")),
        sa.UniqueConstraint(
            "organization_id",
            "membership_id",
            "topic_type",
            "topic_id",
            "event_type",
            name="uq_notification_subscriptions_topic_event",
        ),
    )
    op.create_index(op.f("ix_notification_subscriptions_organization_id"), "notification_subscriptions", ["organization_id"])
    op.create_index(op.f("ix_notification_subscriptions_membership_id"), "notification_subscriptions", ["membership_id"])
    op.create_index(
        "ix_notification_subscriptions_topic",
        "notification_subscriptions",
        ["organization_id", "topic_type", "topic_id", "enabled"],
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("in_app", "email", "push", name="notificationchannel", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "sending",
                "sent",
                "failed",
                "skipped",
                "cancelled",
                name="notificationdeliverystatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("provider_key", sa.String(length=80), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("attempt_count >= 0", name="ck_notification_deliveries_attempt_count"),
        sa.ForeignKeyConstraint(
            ["notification_id", "organization_id"],
            ["notifications.id", "notifications.organization_id"],
            name="fk_notification_deliveries_notification_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_deliveries")),
        sa.UniqueConstraint("notification_id", "channel", name="uq_notification_deliveries_notification_channel"),
    )
    op.create_index(op.f("ix_notification_deliveries_organization_id"), "notification_deliveries", ["organization_id"])
    op.create_index(op.f("ix_notification_deliveries_notification_id"), "notification_deliveries", ["notification_id"])
    op.create_index(op.f("ix_notification_deliveries_scheduled_at"), "notification_deliveries", ["scheduled_at"])
    op.create_index("ix_notification_deliveries_queue", "notification_deliveries", ["status", "scheduled_at", "created_at"])
    op.create_index("ix_notification_deliveries_org_status", "notification_deliveries", ["organization_id", "status"])

    op.create_table(
        "notification_digests",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("in_app", "email", "push", name="notificationchannel", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "frequency",
            sa.Enum("hourly", "daily", "weekly", name="digestfrequency", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "building",
                "ready",
                "sending",
                "sent",
                "failed",
                "cancelled",
                name="notificationdigeststatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_key", sa.String(length=80), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("attempt_count >= 0", name="ck_notification_digests_attempt_count"),
        sa.CheckConstraint("window_end > window_start", name="ck_notification_digests_window"),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_notification_digests_membership_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_digests")),
        sa.UniqueConstraint("id", "organization_id", name="uq_notification_digests_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "membership_id",
            "channel",
            "frequency",
            "window_start",
            "window_end",
            name="uq_notification_digests_delivery_window",
        ),
    )
    op.create_index(op.f("ix_notification_digests_organization_id"), "notification_digests", ["organization_id"])
    op.create_index(op.f("ix_notification_digests_membership_id"), "notification_digests", ["membership_id"])
    op.create_index(op.f("ix_notification_digests_scheduled_at"), "notification_digests", ["scheduled_at"])
    op.create_index("ix_notification_digests_queue", "notification_digests", ["status", "scheduled_at", "created_at"])
    op.create_index("ix_notification_digests_org_status", "notification_digests", ["organization_id", "status"])

    op.create_table(
        "notification_digest_items",
        sa.Column("digest_id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["digest_id", "organization_id"],
            ["notification_digests.id", "notification_digests.organization_id"],
            name="fk_notification_digest_items_digest_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id", "organization_id"],
            ["notifications.id", "notifications.organization_id"],
            name="fk_notification_digest_items_notification_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("digest_id", "notification_id", name=op.f("pk_notification_digest_items")),
        sa.UniqueConstraint("digest_id", "notification_id", name="uq_notification_digest_items_pair"),
    )
    op.create_index(op.f("ix_notification_digest_items_organization_id"), "notification_digest_items", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_digest_items_organization_id"), table_name="notification_digest_items")
    op.drop_table("notification_digest_items")

    op.drop_index("ix_notification_digests_org_status", table_name="notification_digests")
    op.drop_index("ix_notification_digests_queue", table_name="notification_digests")
    op.drop_index(op.f("ix_notification_digests_scheduled_at"), table_name="notification_digests")
    op.drop_index(op.f("ix_notification_digests_membership_id"), table_name="notification_digests")
    op.drop_index(op.f("ix_notification_digests_organization_id"), table_name="notification_digests")
    op.drop_table("notification_digests")

    op.drop_index("ix_notification_deliveries_org_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_queue", table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_scheduled_at"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_notification_id"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_organization_id"), table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("ix_notification_subscriptions_topic", table_name="notification_subscriptions")
    op.drop_index(op.f("ix_notification_subscriptions_membership_id"), table_name="notification_subscriptions")
    op.drop_index(op.f("ix_notification_subscriptions_organization_id"), table_name="notification_subscriptions")
    op.drop_table("notification_subscriptions")

    op.drop_index(op.f("ix_notification_settings_organization_id"), table_name="notification_settings")
    op.drop_table("notification_settings")

    op.drop_index("ix_notification_preferences_org_member", table_name="notification_preferences")
    op.drop_index(op.f("ix_notification_preferences_membership_id"), table_name="notification_preferences")
    op.drop_index(op.f("ix_notification_preferences_organization_id"), table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index("ix_notifications_org_entity", table_name="notifications")
    op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
    op.drop_index(op.f("ix_notifications_entity_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_entity_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_required_permission_key"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_category"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_event_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_recipient_membership_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_organization_id"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_outbox_events_recipient_sequence", table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_recipient_membership_id"), table_name="outbox_events")
    op.drop_constraint("fk_outbox_events_recipient_membership_org", "outbox_events", type_="foreignkey")
    op.drop_column("outbox_events", "recipient_membership_id")
    op.drop_constraint(
        "uq_organization_memberships_id_org",
        "organization_memberships",
        type_="unique",
    )
