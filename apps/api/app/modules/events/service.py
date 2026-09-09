import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models import OutboxEvent, OutboxEventStatus

_MAX_EVENT_PAYLOAD_BYTES = 8 * 1024
_MAX_COLLECTION_ITEMS = 50
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
)


class EventPayloadError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EventPage:
    events: list[OutboxEvent]
    next_cursor: int


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _normalize_value(value: object, depth: int = 0) -> object:
    if depth > 4:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return "[BINARY]"
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                result["_truncated"] = True
                break
            key = str(raw_key)
            result[key] = (
                "[REDACTED]" if _is_sensitive_key(key) else _normalize_value(raw_value, depth + 1)
            )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(item, depth + 1) for item in value[:_MAX_COLLECTION_ITEMS]]
    return str(value)[:500]


def sanitize_event_payload(payload: Mapping[str, object] | None) -> dict[str, object]:
    normalized = _normalize_value(payload or {})
    if not isinstance(normalized, dict):
        raise EventPayloadError("Realtime event payload must be an object")
    encoded = json.dumps(normalized, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > _MAX_EVENT_PAYLOAD_BYTES:
        raise EventPayloadError("Realtime event payload exceeds the 8 KiB safety limit")
    return normalized


async def enqueue_event(
    db: AsyncSession,
    *,
    organization_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: str | UUID | None = None,
    entity_version: int | None = None,
    required_permission_key: str | None = None,
    scope_type: str | None = None,
    scope_id: str | UUID | None = None,
    actor_user_id: UUID | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    payload: Mapping[str, object] | None = None,
    available_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> OutboxEvent:
    if (scope_type is None) != (scope_id is None):
        raise ValueError("scope_type and scope_id must be supplied together")
    if entity_version is not None and entity_version < 1:
        raise ValueError("entity_version must be at least 1")

    event = OutboxEvent(
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_version=entity_version,
        required_permission_key=required_permission_key,
        scope_type=scope_type,
        scope_id=str(scope_id) if scope_id is not None else None,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload=sanitize_event_payload(payload),
        available_at=available_at or datetime.now(UTC),
        expires_at=expires_at,
    )
    db.add(event)
    await db.flush()
    return event


def event_is_visible(
    event: OutboxEvent,
    permission_keys: set[str],
    allowed_scopes: Mapping[str, set[str]] | None = None,
) -> bool:
    if event.required_permission_key and event.required_permission_key not in permission_keys:
        return False
    if event.scope_type is None:
        return True
    if allowed_scopes is None:
        return False
    return event.scope_id in allowed_scopes.get(event.scope_type, set())


async def list_visible_events_after(
    db: AsyncSession,
    *,
    organization_id: UUID,
    after_sequence: int,
    permission_keys: set[str],
    allowed_scopes: Mapping[str, set[str]] | None = None,
    limit: int = 200,
) -> EventPage:
    if after_sequence < 0:
        raise ValueError("after_sequence cannot be negative")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")

    rows = await db.scalars(
        select(OutboxEvent)
        .where(
            OutboxEvent.organization_id == organization_id,
            OutboxEvent.sequence > after_sequence,
        )
        .order_by(OutboxEvent.sequence)
        .limit(min(limit * 4, 1000))
    )
    scanned = rows.all()
    visible: list[OutboxEvent] = []
    next_cursor = after_sequence
    for event in scanned:
        next_cursor = max(next_cursor, event.sequence)
        if event_is_visible(event, permission_keys, allowed_scopes):
            visible.append(event)
            if len(visible) >= limit:
                break
    return EventPage(events=visible, next_cursor=next_cursor)


async def mark_event_published(
    db: AsyncSession,
    event: OutboxEvent,
    *,
    now: datetime | None = None,
) -> None:
    event.status = OutboxEventStatus.PUBLISHED
    event.published_at = now or datetime.now(UTC)
    event.publish_attempts += 1
    event.last_error = None
    await db.flush()


async def mark_event_failed(db: AsyncSession, event: OutboxEvent, error: str) -> None:
    event.status = OutboxEventStatus.FAILED
    event.publish_attempts += 1
    event.last_error = error[:2000]
    await db.flush()
