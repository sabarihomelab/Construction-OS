import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.models import StorageObject, StorageObjectStatus, UploadSession, UploadStatus
from app.modules.files.resumable_models import ResumableUploadState
from app.modules.files.service import (
    FileValidationError,
    begin_upload,
    release_storage_reservation,
)
from app.modules.files.storage import ResumableStorageProvider, UploadTarget

DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024


class UploadOffsetConflict(FileValidationError):
    def __init__(self, expected_offset: int) -> None:
        super().__init__(f"Upload offset mismatch; server has {expected_offset} bytes")
        self.expected_offset = expected_offset


@dataclass(frozen=True, slots=True)
class ResumableUploadSnapshot:
    upload: UploadSession
    state: ResumableUploadState
    target: UploadTarget


def request_hash(
    *,
    context_type: str,
    context_id: UUID,
    filename: str,
    content_type: str | None,
    size_bytes: int,
    sha256: str,
) -> str:
    payload = {
        "context_id": str(context_id),
        "context_type": context_type,
        "content_type": content_type or "",
        "filename": filename,
        "sha256": sha256.lower(),
        "size_bytes": size_bytes,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def begin_or_resume_upload(
    db: AsyncSession,
    *,
    provider: ResumableStorageProvider,
    organization_id: UUID,
    user_id: UUID,
    client_upload_id: UUID,
    context_type: str,
    context_id: UUID,
    original_filename: str,
    declared_content_type: str | None,
    expected_size_bytes: int,
    expected_sha256: str,
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE,
    now: datetime | None = None,
) -> ResumableUploadSnapshot:
    if chunk_size_bytes <= 0:
        raise FileValidationError("Chunk size must be greater than zero")
    now = now or datetime.now(UTC)
    digest = request_hash(
        context_type=context_type,
        context_id=context_id,
        filename=original_filename,
        content_type=declared_content_type,
        size_bytes=expected_size_bytes,
        sha256=expected_sha256,
    )
    state = await db.scalar(
        select(ResumableUploadState)
        .where(
            ResumableUploadState.organization_id == organization_id,
            ResumableUploadState.client_upload_id == client_upload_id,
        )
        .with_for_update()
    )
    if state is not None:
        if state.request_hash != digest or state.context_type != context_type or state.context_id != context_id:
            raise FileValidationError("Client upload ID was reused with different file metadata")
        upload = await db.scalar(
            select(UploadSession)
            .where(
                UploadSession.id == state.upload_session_id,
                UploadSession.organization_id == organization_id,
            )
            .with_for_update()
        )
        if upload is None:
            raise FileValidationError("Resumable upload session was not found")
        if state.cancelled_at is not None:
            raise FileValidationError("Upload was cancelled")
        if upload.status not in {UploadStatus.FINALIZED, UploadStatus.UPLOADED}:
            upload.expires_at = now + timedelta(hours=1)
            upload.status = UploadStatus.UPLOADING
            upload.failure_reason = None
        target = await provider.create_upload_target(
            storage_key=upload.temporary_storage_key,
            content_type=upload.declared_content_type,
            expected_size_bytes=upload.expected_size_bytes,
            expires_at=upload.expires_at,
        )
        return ResumableUploadSnapshot(upload=upload, state=state, target=target)

    existing_object = await db.scalar(
        select(StorageObject).where(
            StorageObject.organization_id == organization_id,
            StorageObject.sha256 == expected_sha256.lower(),
            StorageObject.size_bytes == expected_size_bytes,
            StorageObject.status == StorageObjectStatus.ACTIVE,
        )
    )
    upload, target = await begin_upload(
        db,
        provider=provider,
        organization_id=organization_id,
        user_id=user_id,
        original_filename=original_filename,
        declared_content_type=declared_content_type,
        expected_size_bytes=expected_size_bytes,
        expected_sha256=expected_sha256,
    )
    state = ResumableUploadState(
        upload_session_id=upload.id,
        organization_id=organization_id,
        client_upload_id=client_upload_id,
        context_type=context_type,
        context_id=context_id,
        request_hash=digest,
        chunk_size_bytes=chunk_size_bytes,
        uploaded_bytes=0,
    )
    if existing_object is not None:
        await provider.clone_object(
            source_storage_key=existing_object.storage_key,
            target_storage_key=upload.temporary_storage_key,
        )
        if upload.reserved_bytes > 0:
            await release_storage_reservation(
                db,
                organization_id=organization_id,
                size_bytes=upload.reserved_bytes,
            )
        upload.reserved_bytes = 0
        upload.status = UploadStatus.UPLOADED
        state.uploaded_bytes = expected_size_bytes
        state.deduplicated_storage_object_id = existing_object.id
    db.add(state)
    await db.flush()
    return ResumableUploadSnapshot(upload=upload, state=state, target=target)


async def resumable_status(
    db: AsyncSession,
    *,
    organization_id: UUID,
    upload_id: UUID,
) -> tuple[UploadSession, ResumableUploadState]:
    state = await db.scalar(
        select(ResumableUploadState).where(
            ResumableUploadState.upload_session_id == upload_id,
            ResumableUploadState.organization_id == organization_id,
        )
    )
    upload = await db.scalar(
        select(UploadSession).where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == organization_id,
        )
    )
    if state is None or upload is None:
        raise FileValidationError("Resumable upload session was not found")
    return upload, state


async def append_resumable_chunk(
    db: AsyncSession,
    *,
    provider: ResumableStorageProvider,
    organization_id: UUID,
    upload_id: UUID,
    offset: int,
    chunk: bytes,
    chunk_sha256: str,
) -> tuple[UploadSession, ResumableUploadState]:
    state = await db.scalar(
        select(ResumableUploadState)
        .where(
            ResumableUploadState.upload_session_id == upload_id,
            ResumableUploadState.organization_id == organization_id,
        )
        .with_for_update()
    )
    upload = await db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == organization_id,
        )
        .with_for_update()
    )
    if state is None or upload is None:
        raise FileValidationError("Resumable upload session was not found")
    if state.cancelled_at is not None:
        raise FileValidationError("Upload was cancelled")
    if upload.status == UploadStatus.FINALIZED:
        return upload, state
    if state.uploaded_bytes != offset:
        raise UploadOffsetConflict(state.uploaded_bytes)
    if not chunk:
        raise FileValidationError("Upload chunk is empty")
    expected_size = upload.expected_size_bytes
    if expected_size is None:
        raise FileValidationError("Resumable uploads require a known file size")
    remaining = expected_size - state.uploaded_bytes
    if remaining <= 0:
        upload.status = UploadStatus.UPLOADED
        return upload, state
    if len(chunk) > min(state.chunk_size_bytes, remaining):
        raise FileValidationError("Upload chunk exceeds the allowed chunk size")
    digest = hashlib.sha256(chunk).hexdigest()
    if digest != chunk_sha256.lower():
        raise FileValidationError("Upload chunk checksum mismatch")
    confirmed = await provider.write_upload_chunk(
        storage_key=upload.temporary_storage_key,
        offset=offset,
        content=chunk,
    )
    state.uploaded_bytes = confirmed
    if confirmed == expected_size:
        upload.status = UploadStatus.UPLOADED
    elif confirmed < expected_size:
        upload.status = UploadStatus.UPLOADING
    else:
        raise FileValidationError("Uploaded bytes exceed the expected file size")
    await db.flush()
    return upload, state


async def mark_resumable_finalized(
    db: AsyncSession,
    *,
    organization_id: UUID,
    upload_id: UUID,
    asset_id: UUID,
    version: int,
) -> None:
    state = await db.scalar(
        select(ResumableUploadState)
        .where(
            ResumableUploadState.upload_session_id == upload_id,
            ResumableUploadState.organization_id == organization_id,
        )
        .with_for_update()
    )
    if state is None:
        return
    state.finalized_asset_id = asset_id
    state.finalized_version = version
    await db.flush()


async def cancel_resumable_upload(
    db: AsyncSession,
    *,
    provider: ResumableStorageProvider,
    organization_id: UUID,
    upload_id: UUID,
    now: datetime | None = None,
) -> tuple[UploadSession, ResumableUploadState]:
    now = now or datetime.now(UTC)
    state = await db.scalar(
        select(ResumableUploadState)
        .where(
            ResumableUploadState.upload_session_id == upload_id,
            ResumableUploadState.organization_id == organization_id,
        )
        .with_for_update()
    )
    upload = await db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == organization_id,
        )
        .with_for_update()
    )
    if state is None or upload is None:
        raise FileValidationError("Resumable upload session was not found")
    if upload.status == UploadStatus.FINALIZED or state.finalized_asset_id is not None:
        return upload, state
    if state.cancelled_at is not None:
        return upload, state
    await provider.delete_object(upload.temporary_storage_key)
    if upload.reserved_bytes > 0:
        await release_storage_reservation(
            db,
            organization_id=organization_id,
            size_bytes=upload.reserved_bytes,
        )
    upload.reserved_bytes = 0
    upload.status = UploadStatus.FAILED
    upload.failure_reason = "cancelled_by_user"
    state.cancelled_at = now
    await db.flush()
    return upload, state
