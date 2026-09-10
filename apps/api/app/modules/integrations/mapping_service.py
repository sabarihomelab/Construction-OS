from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.integrations.mapping_models import (
    IntegrationConflict,
    IntegrationConflictStatus,
    MappingProfile,
    MappingProfileVersion,
    MappingVersionStatus,
    SyncCheckpoint,
)


class MappingValidationError(ValueError):
    pass


class CheckpointConflictError(MappingValidationError):
    pass


def validate_mapping_spec(spec: Mapping[str, object]) -> None:
    fields = spec.get("fields")
    if not isinstance(fields, list) or not fields:
        raise MappingValidationError("Mapping profile must define at least one field mapping")
    target_keys: set[str] = set()
    for item in fields:
        if not isinstance(item, Mapping):
            raise MappingValidationError("Each field mapping must be an object")
        source = item.get("source")
        target = item.get("target")
        if not isinstance(source, str) or not source.strip():
            raise MappingValidationError("Field mapping source is required")
        if not isinstance(target, str) or not target.strip():
            raise MappingValidationError("Field mapping target is required")
        normalized_target = target.strip()
        if normalized_target in target_keys:
            raise MappingValidationError(
                f"Mapping profile writes target field more than once: {normalized_target}"
            )
        target_keys.add(normalized_target)


async def publish_mapping_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MappingProfileVersion:
    version = await db.scalar(
        select(MappingProfileVersion)
        .where(
            MappingProfileVersion.id == version_id,
            MappingProfileVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if version is None or version.status != MappingVersionStatus.DRAFT:
        raise MappingValidationError("Draft mapping version was not found")
    validate_mapping_spec(version.mapping_spec)

    profile = await db.scalar(
        select(MappingProfile)
        .where(
            MappingProfile.id == version.profile_id,
            MappingProfile.organization_id == organization_id,
            MappingProfile.active.is_(True),
        )
        .with_for_update()
    )
    if profile is None:
        raise MappingValidationError("Active mapping profile was not found")

    active_versions = list(
        (
            await db.scalars(
                select(MappingProfileVersion).where(
                    MappingProfileVersion.organization_id == organization_id,
                    MappingProfileVersion.profile_id == profile.id,
                    MappingProfileVersion.status == MappingVersionStatus.ACTIVE,
                )
            )
        ).all()
    )
    for active in active_versions:
        active.status = MappingVersionStatus.RETIRED

    version.status = MappingVersionStatus.ACTIVE
    version.published_at = datetime.now(UTC)
    version.published_by_user_id = actor_user_id
    profile.current_version = version.version
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="integration.mapping_version.published",
        target_type="mapping_profile",
        target_id=str(profile.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "version": version.version,
            "source_type": profile.source_type,
            "target_type": profile.target_type,
        },
    )
    return version


async def advance_sync_checkpoint(
    db: AsyncSession,
    *,
    organization_id: UUID,
    connector_id: UUID,
    stream_key: str,
    cursor: str | None,
    source_version: str | None,
    expected_revision: int | None,
) -> SyncCheckpoint:
    normalized_stream = stream_key.strip()
    if not normalized_stream:
        raise MappingValidationError("Sync stream key is required")
    if cursor is not None and len(cursor) > 1024:
        raise MappingValidationError("Sync cursor exceeds the supported length")

    checkpoint = await db.scalar(
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.organization_id == organization_id,
            SyncCheckpoint.connector_id == connector_id,
            SyncCheckpoint.stream_key == normalized_stream,
        )
        .with_for_update()
    )
    if checkpoint is None:
        if expected_revision not in (None, 0):
            raise CheckpointConflictError("Sync checkpoint does not exist at expected revision")
        checkpoint = SyncCheckpoint(
            organization_id=organization_id,
            connector_id=connector_id,
            stream_key=normalized_stream,
            cursor=cursor,
            source_version=source_version,
            revision=1,
            advanced_at=datetime.now(UTC),
        )
        db.add(checkpoint)
        await db.flush()
        return checkpoint

    if expected_revision is None or checkpoint.revision != expected_revision:
        raise CheckpointConflictError(
            f"Sync checkpoint changed from revision {expected_revision} to {checkpoint.revision}"
        )
    checkpoint.cursor = cursor
    checkpoint.source_version = source_version
    checkpoint.revision += 1
    checkpoint.advanced_at = datetime.now(UTC)
    await db.flush()
    return checkpoint


async def create_integration_conflict(
    db: AsyncSession,
    *,
    organization_id: UUID,
    connector_id: UUID,
    external_type: str,
    external_id: str,
    reason_code: str,
    source_values: Mapping[str, object],
    internal_values: Mapping[str, object],
    internal_type: str | None = None,
    internal_id: str | None = None,
) -> IntegrationConflict:
    if not external_type.strip() or not external_id.strip() or not reason_code.strip():
        raise MappingValidationError("Conflict source identity and reason are required")
    conflict = IntegrationConflict(
        organization_id=organization_id,
        connector_id=connector_id,
        external_type=external_type.strip(),
        external_id=external_id.strip(),
        internal_type=internal_type.strip() if internal_type else None,
        internal_id=internal_id.strip() if internal_id else None,
        status=IntegrationConflictStatus.OPEN,
        reason_code=reason_code.strip(),
        source_values=dict(source_values),
        internal_values=dict(internal_values),
    )
    db.add(conflict)
    await db.flush()
    return conflict


async def resolve_integration_conflict(
    db: AsyncSession,
    *,
    organization_id: UUID,
    conflict_id: UUID,
    actor_user_id: UUID,
    resolution: Mapping[str, object],
    note: str | None = None,
    ignore: bool = False,
) -> IntegrationConflict:
    conflict = await db.scalar(
        select(IntegrationConflict)
        .where(
            IntegrationConflict.id == conflict_id,
            IntegrationConflict.organization_id == organization_id,
        )
        .with_for_update()
    )
    if conflict is None:
        raise MappingValidationError("Integration conflict was not found")
    if conflict.status != IntegrationConflictStatus.OPEN:
        return conflict
    if not ignore and not resolution:
        raise MappingValidationError("Conflict resolution is required")

    conflict.status = (
        IntegrationConflictStatus.IGNORED if ignore else IntegrationConflictStatus.RESOLVED
    )
    conflict.resolution = dict(resolution)
    conflict.resolved_by_user_id = actor_user_id
    conflict.resolved_at = datetime.now(UTC)
    conflict.resolution_note = note.strip() if note else None
    await db.flush()
    return conflict
