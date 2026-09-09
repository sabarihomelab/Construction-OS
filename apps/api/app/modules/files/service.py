from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.files.models import (
    FileAsset,
    FileAssetStatus,
    FileSourceType,
    FileVersion,
    OrganizationStorageUsage,
    StorageObject,
    StorageObjectKind,
    StorageObjectStatus,
    UploadSession,
    UploadStatus,
)
from app.modules.files.storage import StorageProvider, UploadTarget
from app.modules.organizations.models import OrganizationSettings


class FileValidationError(ValueError):
    pass


class StorageCapacityError(FileValidationError):
    pass


async def _locked_storage_usage(
    db: AsyncSession,
    organization_id: UUID,
) -> OrganizationStorageUsage:
    usage = await db.scalar(
        select(OrganizationStorageUsage)
        .where(OrganizationStorageUsage.organization_id == organization_id)
        .with_for_update()
    )
    if usage is None:
        usage = OrganizationStorageUsage(organization_id=organization_id)
        db.add(usage)
        await db.flush()
    return usage


async def reserve_storage(
    db: AsyncSession,
    *,
    organization_id: UUID,
    size_bytes: int,
) -> OrganizationStorageUsage:
    if size_bytes < 0:
        raise FileValidationError("Storage reservation cannot be negative")

    usage = await _locked_storage_usage(db, organization_id)
    settings = await db.get(OrganizationSettings, organization_id)
    quota = settings.storage_quota_bytes if settings is not None else None
    if quota is not None and usage.committed_bytes + usage.reserved_bytes + size_bytes > quota:
        raise StorageCapacityError("The configured company storage limit would be exceeded")

    usage.reserved_bytes += size_bytes
    usage.revision += 1
    await db.flush()
    return usage


async def release_storage_reservation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    size_bytes: int,
) -> OrganizationStorageUsage:
    if size_bytes < 0:
        raise FileValidationError("Storage reservation release cannot be negative")

    usage = await _locked_storage_usage(db, organization_id)
    if size_bytes > usage.reserved_bytes:
        raise FileValidationError("Storage reservation accounting would become negative")
    usage.reserved_bytes -= size_bytes
    usage.revision += 1
    await db.flush()
    return usage


async def begin_upload(
    db: AsyncSession,
    *,
    provider: StorageProvider,
    organization_id: UUID,
    user_id: UUID,
    original_filename: str,
    declared_content_type: str | None,
    expected_size_bytes: int | None,
    expected_sha256: str | None = None,
    expires_in: timedelta = timedelta(hours=1),
    now: datetime | None = None,
) -> tuple[UploadSession, UploadTarget]:
    if not original_filename.strip():
        raise FileValidationError("Filename is required")
    if expected_size_bytes is not None and expected_size_bytes <= 0:
        raise FileValidationError("Expected file size must be greater than zero")
    if expected_sha256 is not None:
        expected_sha256 = expected_sha256.lower()
        if len(expected_sha256) != 64 or any(char not in "0123456789abcdef" for char in expected_sha256):
            raise FileValidationError("Expected SHA-256 must be a 64-character hexadecimal digest")
    if expires_in <= timedelta(0):
        raise FileValidationError("Upload expiry must be in the future")

    settings = await db.get(OrganizationSettings, organization_id)
    if settings is not None and settings.storage_quota_bytes is not None and expected_size_bytes is None:
        raise FileValidationError("Expected file size is required when a storage limit is configured")

    reserved_bytes = expected_size_bytes or 0
    await reserve_storage(
        db,
        organization_id=organization_id,
        size_bytes=reserved_bytes,
    )

    now = now or datetime.now(UTC)
    upload_id = uuid4()
    storage_key = f"organizations/{organization_id}/objects/{upload_id}"
    expires_at = now + expires_in
    upload = UploadSession(
        id=upload_id,
        organization_id=organization_id,
        user_id=user_id,
        provider_key=provider.provider_key,
        temporary_storage_key=storage_key,
        original_filename=original_filename.strip(),
        declared_content_type=declared_content_type,
        expected_size_bytes=expected_size_bytes,
        expected_sha256=expected_sha256,
        reserved_bytes=reserved_bytes,
        status=UploadStatus.CREATED,
        expires_at=expires_at,
    )
    db.add(upload)
    await db.flush()

    try:
        target = await provider.create_upload_target(
            storage_key=storage_key,
            content_type=declared_content_type,
            expected_size_bytes=expected_size_bytes,
            expires_at=expires_at,
        )
    except Exception:
        upload.status = UploadStatus.FAILED
        upload.failure_reason = "storage_provider_target_failed"
        await release_storage_reservation(
            db,
            organization_id=organization_id,
            size_bytes=reserved_bytes,
        )
        raise

    upload.status = UploadStatus.UPLOADING
    await db.flush()
    return upload, target


async def finalize_upload(
    db: AsyncSession,
    *,
    provider: StorageProvider,
    upload_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    asset_name: str,
    asset_id: UUID | None = None,
    source_type: FileSourceType = FileSourceType.USER,
    source_system: str | None = None,
    external_id: str | None = None,
    external_version: str | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    now: datetime | None = None,
) -> tuple[FileAsset, FileVersion]:
    now = now or datetime.now(UTC)
    upload = await db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == organization_id,
        )
        .with_for_update()
    )
    if upload is None:
        raise FileValidationError("Upload session was not found")
    if upload.status == UploadStatus.FINALIZED:
        raise FileValidationError("Upload session has already been finalized")
    if upload.status in {UploadStatus.EXPIRED, UploadStatus.FAILED} or now >= upload.expires_at:
        raise FileValidationError("Upload session is no longer active")
    if upload.provider_key != provider.provider_key:
        raise FileValidationError("Upload storage provider does not match the session")

    info = await provider.inspect_object(upload.temporary_storage_key)
    if info.storage_key != upload.temporary_storage_key:
        raise FileValidationError("Storage provider returned an unexpected object identity")
    if info.size_bytes <= 0:
        raise FileValidationError("Uploaded file is empty")
    digest = info.sha256.lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise FileValidationError("Storage provider did not return a valid SHA-256 digest")
    if upload.expected_size_bytes is not None and info.size_bytes != upload.expected_size_bytes:
        raise FileValidationError("Uploaded file size does not match the expected size")
    if upload.expected_sha256 is not None and digest != upload.expected_sha256:
        raise FileValidationError("Uploaded file checksum does not match the expected checksum")

    usage = await _locked_storage_usage(db, organization_id)
    if info.size_bytes > upload.reserved_bytes:
        settings = await db.get(OrganizationSettings, organization_id)
        quota = settings.storage_quota_bytes if settings is not None else None
        additional = info.size_bytes - upload.reserved_bytes
        if quota is not None and usage.committed_bytes + usage.reserved_bytes + additional > quota:
            raise StorageCapacityError("The configured company storage limit would be exceeded")

    stored_object = await db.scalar(
        select(StorageObject).where(
            StorageObject.organization_id == organization_id,
            StorageObject.sha256 == digest,
            StorageObject.size_bytes == info.size_bytes,
            StorageObject.status == StorageObjectStatus.ACTIVE,
        )
    )
    physical_bytes_added = stored_object is None
    if stored_object is None:
        stored_object = StorageObject(
            organization_id=organization_id,
            provider_key=provider.provider_key,
            storage_key=upload.temporary_storage_key,
            kind=StorageObjectKind.ORIGINAL,
            sha256=digest,
            size_bytes=info.size_bytes,
            status=StorageObjectStatus.ACTIVE,
            last_verified_at=now,
        )
        db.add(stored_object)
        await db.flush()
    else:
        await enqueue_event(
            db,
            organization_id=organization_id,
            event_type="storage.duplicate_object.cleanup_requested",
            entity_type="upload_session",
            entity_id=upload.id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            correlation_id=correlation_id,
            payload={
                "provider_key": provider.provider_key,
                "storage_key": upload.temporary_storage_key,
            },
        )

    if asset_id is None:
        if not asset_name.strip():
            raise FileValidationError("Asset name is required")
        asset = FileAsset(
            organization_id=organization_id,
            name=asset_name.strip(),
            current_version=1,
            created_by_user_id=actor_user_id,
        )
        db.add(asset)
        await db.flush()
        version_number = 1
    else:
        asset = await db.scalar(
            select(FileAsset)
            .where(
                FileAsset.id == asset_id,
                FileAsset.organization_id == organization_id,
                FileAsset.status == FileAssetStatus.ACTIVE,
            )
            .with_for_update()
        )
        if asset is None:
            raise FileValidationError("Active file asset was not found")
        version_number = asset.current_version + 1
        asset.current_version = version_number

    version = FileVersion(
        organization_id=organization_id,
        asset_id=asset.id,
        version=version_number,
        storage_object_id=stored_object.id,
        original_filename=upload.original_filename,
        declared_content_type=upload.declared_content_type,
        detected_content_type=info.detected_content_type,
        size_bytes=info.size_bytes,
        sha256=digest,
        source_type=source_type,
        source_system=source_system,
        external_id=external_id,
        external_version=external_version,
        source_metadata={},
        created_by_user_id=actor_user_id,
    )
    db.add(version)

    usage.reserved_bytes -= upload.reserved_bytes
    if usage.reserved_bytes < 0:
        raise FileValidationError("Storage reservation accounting would become negative")
    if physical_bytes_added:
        usage.committed_bytes += info.size_bytes
        usage.object_count += 1
    usage.revision += 1

    upload.status = UploadStatus.FINALIZED
    upload.finalized_at = now
    upload.reserved_bytes = 0

    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="file.version.created",
        target_type="file_asset",
        target_id=str(asset.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        changes={
            "version": version_number,
            "filename": upload.original_filename,
            "size_bytes": info.size_bytes,
            "sha256": digest,
            "source_type": source_type.value,
        },
        metadata={"physical_bytes_added": physical_bytes_added},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="file.version.processing",
        entity_type="file_asset",
        entity_id=asset.id,
        entity_version=version_number,
        required_permission_key="files.file.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"version": version_number, "processing_status": "pending"},
    )
    return asset, version
