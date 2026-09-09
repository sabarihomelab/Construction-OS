from uuid import uuid4

import pytest

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.events.models import OutboxEvent
from app.modules.events.service import EventPayloadError, event_is_visible, sanitize_event_payload
from app.modules.offline.service import canonical_request_hash


def test_realtime_and_offline_tables_are_registered() -> None:
    expected = {
        "outbox_events",
        "client_devices",
        "device_sync_state",
        "sync_mutation_receipts",
        "sync_conflicts",
    }
    assert expected.issubset(Base.metadata.tables.keys())


def test_realtime_payload_redacts_secret_like_keys() -> None:
    sanitized = sanitize_event_payload(
        {
            "entity_id": "123",
            "access_token": "do-not-store",
            "nested": {"password": "secret", "status": "ready"},
        }
    )
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"] == {"password": "[REDACTED]", "status": "ready"}


def test_realtime_payload_rejects_oversized_payload() -> None:
    with pytest.raises(EventPayloadError):
        sanitize_event_payload({"text": "x" * (9 * 1024)})


def test_realtime_event_requires_permission_when_declared() -> None:
    event = OutboxEvent(
        organization_id=uuid4(),
        event_type="rfi.updated",
        entity_type="rfi",
        required_permission_key="rfi.view",
        payload={},
    )
    assert not event_is_visible(event, set())
    assert event_is_visible(event, {"rfi.view"})


def test_scoped_realtime_event_defaults_to_deny_without_scope_context() -> None:
    event = OutboxEvent(
        organization_id=uuid4(),
        event_type="rfi.updated",
        entity_type="rfi",
        required_permission_key="rfi.view",
        scope_type="project",
        scope_id="project-123",
        payload={},
    )
    assert not event_is_visible(event, {"rfi.view"})
    assert event_is_visible(event, {"rfi.view"}, {"project": {"project-123"}})


def test_offline_request_hash_is_order_independent() -> None:
    left = canonical_request_hash({"entity": "daily_log", "value": 10})
    right = canonical_request_hash({"value": 10, "entity": "daily_log"})
    assert left == right


def test_mutation_receipt_does_not_store_full_request_payload() -> None:
    table = Base.metadata.tables["sync_mutation_receipts"]
    assert "request_hash" in table.c
    assert "request_payload" not in table.c
    assert "payload" not in table.c


def test_conflict_keeps_both_sides_for_resolution() -> None:
    table = Base.metadata.tables["sync_conflicts"]
    assert "client_patch" in table.c
    assert "server_values" in table.c
    assert "resolution" in table.c
