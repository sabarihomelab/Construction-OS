from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field.dpr_photo_resumable_schemas import (
    DPRPhotoChunkRead,
    DPRPhotoResumableFinalize,
    DPRPhotoResumableSessionRead,
    DPRPhotoResumableStart,
)
from app.modules.field.dpr_photo_schemas import DPRPhotoRead
from app.modules.field.dpr_photo_service import (
    DPRPhotoConflictError,
    DPRPhotoValidationError,
    finalize_dpr_photo,
    require_draft_report,
    require_photo_section_enabled,
)
from app.modules.files.local_provider import LocalStorageProviderError, configured_storage_provider
from app.modules.files.models import UploadSession, UploadStatus
from app.modules.files.resumable_models import ResumableUploadState
from app.modules.files.resumable_service import (
    UploadOffsetConflict,
    append_resumable_chunk,
    begin_or_resume_upload,
    cancel_resumable_upload,
    mark_resumable_finalized,
    resumable_status,
)
from app.modules.files.service import FileValidationError, StorageCapacityError
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["daily-progress-report-photo-resumable"])

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


def _require_permission(context, project_id: UUID, permission_key: str) -> None:
    project_permissions = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, (DPRPhotoConflictError, UploadOffsetConflict)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            DPRPhotoValidationError,
            FileValidationError,
            StorageCapacityError,
            LocalStorageProviderError,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    raise exc


async def _owned_state(
    db: DbSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    report_id: UUID,
    upload_id: UUID,
) -> tuple[UploadSession, ResumableUploadState]:
    upload, state = await resumable_status(
        db,
        organization_id=organization_id,
        upload_id=upload_id,
    )
    if upload.user_id != user_id or state.context_type != "daily_report_photo" or state.context_id != report_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo upload session not found")
    return upload, state


def _session_read(upload: UploadSession, state: ResumableUploadState) -> DPRPhotoResumableSessionRead:
    return DPRPhotoResumableSessionRead(
        upload_id=upload.id,
        client_photo_id=state.client_upload_id,
        status=upload.status.value,
        uploaded_bytes=state.uploaded_bytes,
        size_bytes=upload.expected_size_bytes or 0,
        chunk_size_bytes=state.chunk_size_bytes,
        content_already_present=state.deduplicated_storage_object_id is not None,
        expires_at=upload.expires_at,
        finalized_asset_id=state.finalized_asset_id,
        finalized_version=state.finalized_version,
    )


@router.post(
    "/projects/{project_id}/daily-reports/{report_id}/photos/resumable",
    response_model=DPRPhotoResumableSessionRead,
)
async def start_resumable_photo_upload(
    project_id: UUID,
    report_id: UUID,
    payload: DPRPhotoResumableStart,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DPRPhotoResumableSessionRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")
    content_type = payload.content_type.strip().lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="DPR photos must be JPEG, PNG, WebP, HEIC or HEIF images",
        )
    try:
        await require_photo_section_enabled(
            db,
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            project_id=project_id,
        )
        await require_draft_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
        )
        snapshot = await begin_or_resume_upload(
            db,
            provider=configured_storage_provider(),
            organization_id=context.organization_id,
            user_id=session.user_id,
            client_upload_id=payload.client_photo_id,
            context_type="daily_report_photo",
            context_id=report_id,
            original_filename=payload.original_filename,
            declared_content_type=content_type,
            expected_size_bytes=payload.size_bytes,
            expected_sha256=payload.sha256,
        )
        await db.commit()
        return _session_read(snapshot.upload, snapshot.state)
    except (DPRPhotoConflictError, DPRPhotoValidationError, FileValidationError, StorageCapacityError, LocalStorageProviderError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}/status",
    response_model=DPRPhotoResumableSessionRead,
)
async def get_resumable_photo_status(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DPRPhotoResumableSessionRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    upload, state = await _owned_state(
        db,
        organization_id=context.organization_id,
        user_id=session.user_id,
        report_id=report_id,
        upload_id=upload_id,
    )
    return _session_read(upload, state)


@router.patch(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}/chunk",
    response_model=DPRPhotoChunkRead,
)
async def upload_resumable_photo_chunk(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    request: Request,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
    upload_offset: int = Header(alias="Upload-Offset", ge=0),
    chunk_sha256: str = Header(alias="X-Chunk-SHA256", min_length=64, max_length=64),
) -> DPRPhotoChunkRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")
    await _owned_state(
        db,
        organization_id=context.organization_id,
        user_id=session.user_id,
        report_id=report_id,
        upload_id=upload_id,
    )
    body = await request.body()
    try:
        upload, state = await append_resumable_chunk(
            db,
            provider=configured_storage_provider(),
            organization_id=context.organization_id,
            upload_id=upload_id,
            offset=upload_offset,
            chunk=body,
            chunk_sha256=chunk_sha256,
        )
        await db.commit()
        size = upload.expected_size_bytes or 0
        return DPRPhotoChunkRead(
            upload_id=upload.id,
            status=upload.status.value,
            uploaded_bytes=state.uploaded_bytes,
            size_bytes=size,
            complete=state.uploaded_bytes == size and size > 0,
        )
    except (UploadOffsetConflict, FileValidationError, LocalStorageProviderError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}/resumable-finalize",
    response_model=DPRPhotoRead,
)
async def finalize_resumable_photo_upload(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    payload: DPRPhotoResumableFinalize,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DPRPhotoRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")
    try:
        upload, state = await _owned_state(
            db,
            organization_id=context.organization_id,
            user_id=session.user_id,
            report_id=report_id,
            upload_id=upload_id,
        )
        expected_size = upload.expected_size_bytes or 0
        if upload.status != UploadStatus.FINALIZED and state.uploaded_bytes != expected_size:
            raise FileValidationError("Photo upload is incomplete")
        report, link, version = await finalize_dpr_photo(
            db,
            provider=configured_storage_provider(),
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            membership_id=context.membership_id,
            upload_id=upload_id,
            expected_revision=payload.expected_revision,
            client_photo_id=payload.client_photo_id,
            caption=payload.caption,
            captured_at=payload.captured_at,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await mark_resumable_finalized(
            db,
            organization_id=context.organization_id,
            upload_id=upload_id,
            asset_id=version.asset_id,
            version=version.version,
        )
        await db.commit()
        await db.refresh(link)
        metadata = version.source_metadata or {}
        return DPRPhotoRead(
            asset_id=version.asset_id,
            version=version.version,
            filename=version.original_filename,
            content_type=version.detected_content_type or version.declared_content_type,
            size_bytes=version.size_bytes,
            relation_type=link.relation_type,
            client_photo_id=metadata.get("client_photo_id"),
            caption=metadata.get("caption"),
            captured_at=metadata.get("captured_at"),
            created_at=link.created_at,
            report_revision=report.revision,
        )
    except (DPRPhotoConflictError, DPRPhotoValidationError, FileValidationError, LocalStorageProviderError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.delete(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}/resumable",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_resumable_photo_upload_route(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    await _owned_state(
        db,
        organization_id=context.organization_id,
        user_id=session.user_id,
        report_id=report_id,
        upload_id=upload_id,
    )
    try:
        await cancel_resumable_upload(
            db,
            provider=configured_storage_provider(),
            organization_id=context.organization_id,
            upload_id=upload_id,
        )
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (FileValidationError, LocalStorageProviderError) as exc:
        await db.rollback()
        _raise_domain_error(exc)
