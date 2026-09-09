from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditEvent, AuditRisk

REDACTED = "[REDACTED]"
MAX_STRING_LENGTH = 4096
MAX_LIST_ITEMS = 50
MAX_DEPTH = 6
SENSITIVE_KEY_PARTS = {
    "password",
    "token",
    "secret",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
    "recovery_code",
    "file_content",
    "base64",
    "binary",
    "blob",
}


def _key_is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def sanitize_audit_value(value: object, *, depth: int = 0) -> object:
    if depth >= MAX_DEPTH:
        return "[MAX_DEPTH]"

    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            sanitized[key] = (
                REDACTED
                if _key_is_sensitive(key)
                else sanitize_audit_value(raw_value, depth=depth + 1)
            )
        return sanitized

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value[:MAX_LIST_ITEMS])
        sanitized_items = [sanitize_audit_value(item, depth=depth + 1) for item in items]
        if len(value) > MAX_LIST_ITEMS:
            sanitized_items.append("[TRUNCATED]")
        return sanitized_items

    if isinstance(value, (bytes, bytearray)):
        return "[BINARY_OMITTED]"

    if isinstance(value, str):
        if len(value) <= MAX_STRING_LENGTH:
            return value
        return value[:MAX_STRING_LENGTH] + "...[TRUNCATED]"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return str(value)[:MAX_STRING_LENGTH]


async def record_audit_event(
    db: AsyncSession,
    *,
    organization_id: UUID,
    action: str,
    target_type: str,
    actor_type: AuditActorType,
    actor_user_id: UUID | None = None,
    session_id: UUID | None = None,
    target_id: str | None = None,
    correlation_id: UUID | None = None,
    risk: AuditRisk = AuditRisk.LOW,
    reason: str | None = None,
    changes: Mapping[str, object] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        action=action[:180],
        target_type=target_type[:100],
        target_id=target_id[:160] if target_id is not None else None,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=risk,
        reason=reason,
        changes=sanitize_audit_value(changes or {}),
        metadata=sanitize_audit_value(metadata or {}),
    )
    db.add(event)
    await db.flush()
    return event
