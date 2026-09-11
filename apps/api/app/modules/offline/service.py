import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offline.models import (
    ClientDevice,
    DevicePlatform,
    DeviceSyncState,
    SyncConflict,
    SyncConflictStatus,
    SyncMutationOperation,
    SyncMutationReceipt,
    SyncMutationStatus,
)

_MAX_CONFLICT_PAYLOAD_BYTES = 32 * 1024


class OfflineSyncError(ValueError):
    pass


class IdempotencyConflictError(OfflineSyncError):
    pass


def canonical_request_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_conflict_payload(payload: Mapping[str, object], label: str) -> dict[str, object]:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    if len(encoded) > _MAX_CONFLICT_PAYLOAD_BYTES:
        raise OfflineSyncError(f"{label} exceeds the 32 KiB conflict safety limit")
    return dict(payload)


async def register_device(
    db: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    installation_id: str,
    platform: DevicePlatform,
    device_label: str | None = None,
    app_version: str | None = None,
    now: datetime | None = None,
) -> ClientDevice:
    now = now or datetime.now(UTC)
    device = await db.scalar(
        select(ClientDevice).where(
            ClientDevice.organization_id == organization_id,
            ClientDevice.user_id == user_id,
            ClientDevice.installation_id == installation_id,
        )
    )
    if device is None:
        device = ClientDevice(
            organization_id=organization_id,
            user_id=user_id,
            installation_id=installation_id,
            platform=platform,
            device_label=device_label,
            app_version=app_version,
            last_seen_at=now,
        )
        db.add(device)
        await db.flush()
        db.add(DeviceSyncState(device_id=device.id, organization_id=organization_id))
    else:
        if device.revoked_at is not None:
            raise OfflineSyncError("This device registration has been revoked")
        device.platform = platform
        device.device_label = device_label
        device.app_version = app_version
        device.last_seen_at = now

    await db.flush()
    return device


async def begin_mutation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    device_id: UUID,
    client_mutation_id: UUID,
    entity_type: str,
    entity_id: str | UUID | None,
    operation: SyncMutationOperation,
    request_payload: Mapping[str, object],
    base_version: int | None = None,
) -> tuple[SyncMutationReceipt, bool]:
    if base_version is not None and base_version < 1:
        raise OfflineSyncError("base_version must be at least 1")

    device = await db.get(ClientDevice, device_id)
    if (
        device is None
        or device.organization_id != organization_id
        or device.user_id != user_id
        or device.revoked_at is not None
    ):
        raise OfflineSyncError("Active device registration was not found")

    request_hash = canonical_request_hash(request_payload)
    existing = await db.scalar(
        select(SyncMutationReceipt).where(
            SyncMutationReceipt.organization_id == organization_id,
            SyncMutationReceipt.device_id == device_id,
            SyncMutationReceipt.client_mutation_id == client_mutation_id,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The same client mutation ID was reused with different content"
            )
        return existing, True

    receipt = SyncMutationReceipt(
        organization_id=organization_id,
        device_id=device_id,
        client_mutation_id=client_mutation_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        operation=operation,
        base_version=base_version,
        request_hash=request_hash,
    )
    db.add(receipt)
    await db.flush()
    return receipt, False


async def mark_mutation_applied(
    db: AsyncSession,
    receipt: SyncMutationReceipt,
    *,
    server_version: int | None,
    result: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> None:
    if server_version is not None and server_version < 1:
        raise OfflineSyncError("server_version must be at least 1")
    receipt.status = SyncMutationStatus.APPLIED
    receipt.server_version = server_version
    receipt.result = dict(result or {})
    receipt.error_code = None
    receipt.completed_at = now or datetime.now(UTC)
    await db.flush()


async def mark_mutation_rejected(
    db: AsyncSession,
    receipt: SyncMutationReceipt,
    *,
    error_code: str,
    result: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> None:
    receipt.status = SyncMutationStatus.REJECTED
    receipt.result = dict(result or {})
    receipt.error_code = error_code[:80]
    receipt.completed_at = now or datetime.now(UTC)
    await db.flush()


async def mark_mutation_conflict(
    db: AsyncSession,
    receipt: SyncMutationReceipt,
    *,
    entity_id: str | UUID,
    base_version: int,
    server_version: int,
    client_patch: Mapping[str, object],
    server_values: Mapping[str, object],
    result: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> SyncConflict:
    if base_version < 1 or server_version < 1:
        raise OfflineSyncError("Conflict versions must be at least 1")

    existing = await db.scalar(
        select(SyncConflict).where(SyncConflict.mutation_receipt_id == receipt.id)
    )
    if existing is not None:
        return existing

    conflict = SyncConflict(
        organization_id=receipt.organization_id,
        device_id=receipt.device_id,
        mutation_receipt_id=receipt.id,
        entity_type=receipt.entity_type,
        entity_id=str(entity_id),
        base_version=base_version,
        server_version=server_version,
        client_patch=_validate_conflict_payload(client_patch, "client_patch"),
        server_values=_validate_conflict_payload(server_values, "server_values"),
    )
    db.add(conflict)
    receipt.status = SyncMutationStatus.CONFLICT
    receipt.server_version = server_version
    receipt.result = dict(result or {})
    receipt.error_code = "version_conflict"
    receipt.completed_at = now or datetime.now(UTC)
    await db.flush()
    return conflict


async def resolve_conflict(
    db: AsyncSession,
    conflict: SyncConflict,
    *,
    resolved_by_user_id: UUID,
    resolution: Mapping[str, object],
    resolution_note: str | None = None,
    dismissed: bool = False,
    now: datetime | None = None,
) -> None:
    if conflict.status != SyncConflictStatus.OPEN:
        raise OfflineSyncError("Conflict is already closed")
    conflict.status = SyncConflictStatus.DISMISSED if dismissed else SyncConflictStatus.RESOLVED
    conflict.resolution = _validate_conflict_payload(resolution, "resolution")
    conflict.resolved_by_user_id = resolved_by_user_id
    conflict.resolved_at = now or datetime.now(UTC)
    conflict.resolution_note = resolution_note
    await db.flush()


async def acknowledge_event_sequence(
    db: AsyncSession,
    *,
    organization_id: UUID,
    device_id: UUID,
    sequence: int,
    now: datetime | None = None,
) -> DeviceSyncState:
    if sequence < 0:
        raise OfflineSyncError("Acknowledged event sequence cannot be negative")

    state = await db.get(DeviceSyncState, device_id)
    if state is None or state.organization_id != organization_id:
        raise OfflineSyncError("Device sync state was not found")
    if sequence > state.last_acknowledged_event_sequence:
        state.last_acknowledged_event_sequence = sequence
        state.revision += 1
    state.last_sync_completed_at = now or datetime.now(UTC)
    await db.flush()
    return state
