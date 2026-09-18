from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.operations.models import (
    HealthState,
    OperationalEvent,
    OperationalEventStatus,
    OperationalHealthSnapshot,
)

_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "private_key",
    "connection_string",
)


class OperationsValidationError(ValueError):
    pass


def _sanitize_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
            result[key] = "[REDACTED]"
        elif isinstance(raw_value, Mapping):
            result[key] = _sanitize_mapping(raw_value)
        elif isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            result[key] = raw_value
        else:
            result[key] = str(raw_value)[:500]
    return result


@dataclass(frozen=True, slots=True)
class HealthObservation:
    category: str
    component_key: str
    state: HealthState
    summary: str
    metrics: Mapping[str, object]
    valid_for: timedelta = timedelta(minutes=5)


HealthCollector = Callable[[AsyncSession, UUID], Awaitable[list[HealthObservation]]]


class HealthCollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, HealthCollector] = {}

    def register(self, key: str, collector: HealthCollector) -> None:
        normalized = key.strip()
        if not normalized:
            raise ValueError("Collector key is required")
        if normalized in self._collectors:
            raise ValueError(f"Health collector already registered for {normalized}")
        self._collectors[normalized] = collector

    def items(self) -> tuple[tuple[str, HealthCollector], ...]:
        return tuple(sorted(self._collectors.items()))


async def record_health_observation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    observation: HealthObservation,
    observed_at: datetime | None = None,
) -> OperationalHealthSnapshot:
    current = observed_at or datetime.now(UTC)
    if not observation.category.strip() or not observation.component_key.strip():
        raise OperationsValidationError("Health category and component are required")
    if observation.valid_for <= timedelta(0):
        raise OperationsValidationError("Health observation validity must be positive")

    snapshot = OperationalHealthSnapshot(
        organization_id=organization_id,
        category=observation.category.strip(),
        component_key=observation.component_key.strip(),
        state=observation.state,
        summary=observation.summary.strip()[:255],
        metrics=_sanitize_mapping(observation.metrics),
        observed_at=current,
        valid_until=current + observation.valid_for,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def record_operational_event(
    db: AsyncSession,
    *,
    organization_id: UUID,
    event_key: str,
    category: str,
    severity: HealthState,
    title: str,
    summary: str,
    source_key: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: Mapping[str, object] | None = None,
    observed_at: datetime | None = None,
) -> OperationalEvent:
    current = observed_at or datetime.now(UTC)
    normalized_key = event_key.strip()
    if not normalized_key:
        raise OperationsValidationError("Operational event key is required")

    event = await db.scalar(
        select(OperationalEvent)
        .where(
            OperationalEvent.organization_id == organization_id,
            OperationalEvent.event_key == normalized_key,
            OperationalEvent.status == OperationalEventStatus.OPEN,
        )
        .order_by(OperationalEvent.last_seen_at.desc())
        .limit(1)
        .with_for_update()
    )
    if event is None:
        event = OperationalEvent(
            organization_id=organization_id,
            event_key=normalized_key,
            category=category.strip(),
            severity=severity,
            title=title.strip()[:180],
            summary=summary.strip(),
            source_key=source_key.strip(),
            entity_type=entity_type,
            entity_id=entity_id,
            occurrence_count=1,
            details=_sanitize_mapping(details or {}),
            first_seen_at=current,
            last_seen_at=current,
        )
        db.add(event)
    else:
        event.severity = severity
        event.title = title.strip()[:180]
        event.summary = summary.strip()
        event.details = _sanitize_mapping(details or {})
        event.last_seen_at = current
        event.occurrence_count += 1
    await db.flush()
    return event


async def resolve_operational_event(
    db: AsyncSession,
    *,
    organization_id: UUID,
    event_id: UUID,
    resolution_summary: str,
    resolved_at: datetime | None = None,
) -> OperationalEvent:
    event = await db.scalar(
        select(OperationalEvent)
        .where(
            OperationalEvent.id == event_id,
            OperationalEvent.organization_id == organization_id,
        )
        .with_for_update()
    )
    if event is None:
        raise OperationsValidationError("Operational event was not found")
    if event.status == OperationalEventStatus.RESOLVED:
        return event

    event.status = OperationalEventStatus.RESOLVED
    event.resolved_at = resolved_at or datetime.now(UTC)
    event.resolution_summary = resolution_summary.strip()[:255]
    await db.flush()
    return event


async def latest_component_health(
    db: AsyncSession,
    *,
    organization_id: UUID,
    category: str,
    component_key: str,
) -> OperationalHealthSnapshot | None:
    return await db.scalar(
        select(OperationalHealthSnapshot)
        .where(
            OperationalHealthSnapshot.organization_id == organization_id,
            OperationalHealthSnapshot.category == category,
            OperationalHealthSnapshot.component_key == component_key,
        )
        .order_by(OperationalHealthSnapshot.observed_at.desc())
        .limit(1)
    )
