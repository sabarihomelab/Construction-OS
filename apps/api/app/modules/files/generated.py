from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.models import (
    FileAsset,
    FileAssetStatus,
    FileProcessingStatus,
    FileScanStatus,
    FileSourceType,
    FileVersion,
    OrganizationStorageUsage,
    StorageObject,
    StorageObjectKind,
    StorageObjectStatus,
)
from app.modules.files.object_store import ObjectStoreError, generated_object_store
from app.modules.files.service import reserve_storage


class GeneratedFileError(ValueError):
    pass


async def store_generated_file(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    filename: str,
    content: bytes,
    content_type: str,
    source_system: str,
    source_metadata: dict[str, object] | None = None,
) -> tuple[FileAsset, FileVersion]:
    if not content:
        raise GeneratedFileError("Generated file content cannot be empty")
    clean_name = filename.strip()
    if not clean_name:
        raise GeneratedFileError("Generated filename is required")

    await reserve_storage(db, organization_id=organization_id, size_bytes=len(content))
    usage = await db.scalar(
        select(OrganizationStorageUsage)
        .where(OrganizationStorageUsage.organization_id == organization_id)
        .with_for_update()
    )
    if usage is None:
        raise GeneratedFileError("Storage usage state was not created")

    import hashlib

    digest = hashlib.sha256(content).hexdigest()
    stored_object = await db.scalar(
        select(StorageObject).where(
            StorageObject.organization_id == organization_id,
            StorageObject.sha256 == digest,
            StorageObject.size_bytes == len(content),
            StorageObject.status == StorageObjectStatus.ACTIVE,
        )
    )
    physical_bytes_added = stored_object is None
    if stored_object is None:
        try:
            stored = await generated_object_store().write_bytes(
                organization_id=organization_id,
                filename=clean_name,
                content=content,
                content_type=content_type,
            )
        except ObjectStoreError as exc:
            raise GeneratedFileError(str(exc)) from exc
        stored_object = StorageObject(
            organization_id=organization_id,
            provider_key=stored.provider_key,
            storage_key=stored.storage_key,
            kind=StorageObjectKind.DERIVATIVE,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            status=StorageObjectStatus.ACTIVE,
            last_verified_at=datetime.now(UTC),
        )
        db.add(stored_object)
        await db.flush()

    if usage.reserved_bytes < len(content):
        raise GeneratedFileError("Storage reservation accounting is inconsistent")
    usage.reserved_bytes -= len(content)
    if physical_bytes_added:
        usage.committed_bytes += len(content)
        usage.object_count += 1
    usage.revision += 1

    asset = FileAsset(
        organization_id=organization_id,
        name=clean_name,
        current_version=1,
        status=FileAssetStatus.ACTIVE,
        created_by_user_id=actor_user_id,
    )
    db.add(asset)
    await db.flush()
    version = FileVersion(
        organization_id=organization_id,
        asset_id=asset.id,
        version=1,
        storage_object_id=stored_object.id,
        original_filename=clean_name,
        declared_content_type=content_type,
        detected_content_type=content_type,
        size_bytes=len(content),
        sha256=digest,
        scan_status=FileScanStatus.CLEAN,
        processing_status=FileProcessingStatus.READY,
        source_type=FileSourceType.SYSTEM,
        source_system=source_system,
        source_metadata=dict(source_metadata or {}),
        created_by_user_id=actor_user_id,
    )
    db.add(version)
    await db.flush()
    return asset, version


async def read_file_version_bytes(
    db: AsyncSession,
    *,
    organization_id: UUID,
    asset_id: UUID,
    version: int,
) -> tuple[FileVersion, bytes]:
    result = await db.execute(
        select(FileVersion, StorageObject, FileAsset)
        .join(
            StorageObject,
            (StorageObject.id == FileVersion.storage_object_id)
            & (StorageObject.organization_id == FileVersion.organization_id),
        )
        .join(
            FileAsset,
            (FileAsset.id == FileVersion.asset_id)
            & (FileAsset.organization_id == FileVersion.organization_id),
        )
        .where(
            FileVersion.organization_id == organization_id,
            FileVersion.asset_id == asset_id,
            FileVersion.version == version,
            FileAsset.status == FileAssetStatus.ACTIVE,
            StorageObject.status == StorageObjectStatus.ACTIVE,
        )
    )
    row = result.first()
    if row is None:
        raise GeneratedFileError("Stored file version was not found")
    file_version, storage_object, _asset = row
    try:
        content = await generated_object_store().read_bytes(storage_object.storage_key)
    except ObjectStoreError as exc:
        raise GeneratedFileError(str(exc)) from exc
    if len(content) != file_version.size_bytes:
        raise GeneratedFileError("Stored file size no longer matches its immutable version")
    return file_version, content
