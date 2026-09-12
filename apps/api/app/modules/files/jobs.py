from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.local_provider import configured_storage_provider
from app.modules.files.models import FileProcessingStatus, FileVersion, StorageObject
from app.modules.jobs.handlers import JobHandlerRegistry
from app.modules.jobs.models import BackgroundJob

FILE_PROCESS_JOB_TYPE = "files.process_version"


async def process_file_version(
    db: AsyncSession,
    job: BackgroundJob,
) -> dict[str, object]:
    raw_version_id = job.payload.get("file_version_id")
    if not isinstance(raw_version_id, str):
        raise TypeError("files.process_version requires file_version_id")
    file_version_id = UUID(raw_version_id)

    row = await db.execute(
        select(FileVersion, StorageObject)
        .join(
            StorageObject,
            (StorageObject.id == FileVersion.storage_object_id)
            & (StorageObject.organization_id == FileVersion.organization_id),
        )
        .where(
            FileVersion.id == file_version_id,
            FileVersion.organization_id == job.organization_id,
        )
        .with_for_update()
    )
    result = row.first()
    if result is None:
        raise ValueError("File version for processing was not found")
    version, storage_object = result

    provider = configured_storage_provider()
    if provider.provider_key != storage_object.provider_key:
        raise ValueError("Installed storage provider does not match the file version")

    info = await provider.inspect_object(storage_object.storage_key)
    if info.storage_key != storage_object.storage_key:
        raise ValueError("Stored file identity changed during processing")
    if info.size_bytes != version.size_bytes:
        version.processing_status = FileProcessingStatus.FAILED
        raise ValueError("Stored file size no longer matches the immutable file version")
    if info.sha256.lower() != version.sha256.lower():
        version.processing_status = FileProcessingStatus.FAILED
        raise ValueError("Stored file checksum no longer matches the immutable file version")

    storage_object.last_verified_at = datetime.now(UTC)
    version.processing_status = FileProcessingStatus.READY
    if version.detected_content_type is None and info.detected_content_type:
        version.detected_content_type = info.detected_content_type
    metadata = dict(version.source_metadata or {})
    metadata["integrity_verified"] = True
    metadata["integrity_verified_at"] = storage_object.last_verified_at.isoformat()
    version.source_metadata = metadata
    await db.flush()

    return {
        "file_version_id": str(version.id),
        "asset_id": str(version.asset_id),
        "processing_status": version.processing_status.value,
        "scan_status": version.scan_status.value,
        "integrity_verified": True,
    }


def register_file_handlers(registry: JobHandlerRegistry) -> None:
    if registry.contains(FILE_PROCESS_JOB_TYPE):
        return
    registry.register(
        FILE_PROCESS_JOB_TYPE,
        process_file_version,
        timeout_seconds=120,
        lease_seconds=30,
        profile="general",
    )
