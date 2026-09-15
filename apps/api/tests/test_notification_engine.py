from datetime import UTC, datetime, time

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.notifications.models import DigestFrequency
from app.modules.notifications.service import next_allowed_delivery_time, next_digest_window


def test_notification_tables_are_registered() -> None:
    expected = {
        "notifications",
        "notification_preferences",
        "notification_settings",
        "notification_subscriptions",
        "notification_deliveries",
        "notification_digests",
        "notification_digest_items",
    }
    assert expected.issubset(Base.metadata.tables)


def test_notification_reason_is_first_class_data() -> None:
    table = Base.metadata.tables["notifications"]
    assert "reason_code" in table.c
    assert "reason_text" in table.c
    assert "category" in table.c


def test_notification_recipient_is_tenant_consistent() -> None:
    table = Base.metadata.tables["notifications"]
    names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_notifications_recipient_membership_org" in names


def test_realtime_event_supports_recipient_membership_scope() -> None:
    table = Base.metadata.tables["outbox_events"]
    assert "recipient_membership_id" in table.c
    names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_outbox_events_recipient_membership_org" in names


def test_overnight_quiet_hours_delay_until_local_end() -> None:
    now = datetime(2026, 9, 10, 18, 0, tzinfo=UTC)  # 23:30 in India
    allowed = next_allowed_delivery_time(
        now,
        timezone_name="Asia/Kolkata",
        quiet_hours_enabled=True,
        quiet_start=time(22, 0),
        quiet_end=time(7, 0),
    )
    assert allowed == datetime(2026, 9, 11, 1, 30, tzinfo=UTC)


def test_delivery_outside_quiet_hours_is_not_delayed() -> None:
    now = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)  # 13:30 in India
    allowed = next_allowed_delivery_time(
        now,
        timezone_name="Asia/Kolkata",
        quiet_hours_enabled=True,
        quiet_start=time(22, 0),
        quiet_end=time(7, 0),
    )
    assert allowed == now


def test_daily_digest_window_uses_recipient_timezone() -> None:
    now = datetime(2026, 9, 10, 3, 0, tzinfo=UTC)  # 08:30 in India
    start, end = next_digest_window(
        now,
        timezone_name="Asia/Kolkata",
        frequency=DigestFrequency.DAILY,
        digest_time=time(8, 0),
    )
    assert start == datetime(2026, 9, 10, 2, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 11, 2, 30, tzinfo=UTC)


def test_digest_items_keep_tenant_consistent_links() -> None:
    table = Base.metadata.tables["notification_digest_items"]
    names = {constraint.name for constraint in table.foreign_key_constraints}
    assert "fk_notification_digest_items_digest_org" in names
    assert "fk_notification_digest_items_notification_org" in names
