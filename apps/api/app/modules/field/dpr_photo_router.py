from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field.dpr_photo_schemas import (
    DPRPhotoChangeRead,
    DPRPhotoFinalize,
    DPRPhotoRead,
    DPRPhotoUploadSessionRead,
    DPRPhotoUploadStart,
    DPRPhotoUploadTargetRead,
)
from app.modules.field.dpr_photo_service import (
    DPRPhotoConflictError,
    DPRPhotoValidationError,
    finalize_dpr_photo,
    list_dpr_photos,
    remove_dpr_photo,
    require_draft_report,
    require_photo_section_enabled,
)
from app.modules.field.models import DailyReport, DailyReportStatus
from app.modules.files.local_provider import (
    LocalStorageProviderError,
    configured_storage_provider,
)
from app.modules.files.models import UploadSession, UploadStatus
from app.modules.files.service import (
    FileValidationError,
    StorageCapacityError,
    begin_upload,
    release_storage_reservation,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["daily-progress-report-photos"])

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _require_permission(context, project_id: UUID, permission_key: str) -> None:
    project_permissions = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, DPRPhotoConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(
        exc,
        (DPRPhotoValidationError, FileValidationError, StorageCapacityError, LocalStorageProviderError),
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    raise exc


async def _require_existing_draft(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> DailyReport:
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily Report not found")
    if report.status != DailyReportStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Photos can only be changed while the Daily Report is a draft",
        )
    return report


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/photos",
    response_model=list[DPRPhotoRead],
)
async def get_dpr_photos(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[dict[str, object]]:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    try:
        _report, rows = await list_dpr_photos(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
        )
        return rows
    except DPRPhotoValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads",
    response_model=DPRPhotoUploadSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def start_dpr_photo_upload(
    project_id: UUID,
    report_id: UUID,
    payload: DPRPhotoUploadStart,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DPRPhotoUploadSessionRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")

    normalized_type = payload.content_type.strip().lower()
    if normalized_type not in _ALLOWED_CONTENT_TYPES:
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
        provider = configured_storage_provider()
        upload, target = await begin_upload(
            db,
            provider=provider,
            organization_id=context.organization_id,
            user_id=session.user_id,
            original_filename=Path(payload.original_filename).name,
            declared_content_type=normalized_type,
            expected_size_bytes=payload.size_bytes,
            expected_sha256=payload.sha256,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        _domain_error(exc)

    target_url = target.url
    if provider.provider_key == "local":
        target_url = (
            f"/api/v1/projects/{project_id}/daily-reports/{report_id}/"
            f"photos/uploads/{upload.id}/content"
        )
    return DPRPhotoUploadSessionRead(
        upload_id=upload.id,
        client_photo_id=payload.client_photo_id,
        target=DPRPhotoUploadTargetRead(
            url=target_url,
            method=target.method,
            headers=target.headers,
            expires_at=target.expires_at,
        ),
    )


@router.put(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}/content",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_dpr_photo_content(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    request: Request,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")
    await _require_existing_draft(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_id=report_id,
    )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length") from exc
        if declared_length <= 0 or declared_length > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Photo is too large")

    upload = await db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == context.organization_id,
            UploadSession.user_id == session.user_id,
        )
        .with_for_update()
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo upload session not found")
    if upload.status not in {UploadStatus.UPLOADING, UploadStatus.UPLOADED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Photo upload session is not writable")
    if datetime.now(UTC) >= upload.expires_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Photo upload session expired")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Photo content is empty")
    if len(body) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Photo is too large")
    if upload.expected_size_bytes is not None and len(body) != upload.expected_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Photo size does not match the upload session",
        )

    try:
        provider = configured_storage_provider()
        if upload.provider_key != provider.provider_key:
            raise DPRPhotoValidationError("Photo upload storage provider changed")
        await provider.write_upload_bytes(storage_key=upload.temporary_storage_key, content=body)
        upload.status = UploadStatus.UPLOADED
        await db.commit()
    except Exception as exc:
        await db.rollback()
        _domain_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}/finalize",
    response_model=DPRPhotoRead,
)
async def finalize_dpr_photo_upload(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    payload: DPRPhotoFinalize,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DPRPhotoRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")
    try:
        provider = configured_storage_provider()
        report, link, version = await finalize_dpr_photo(
            db,
            provider=provider,
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
        await db.commit()
        await db.refresh(link)
    except Exception as exc:
        await db.rollback()
        _domain_error(exc)

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


@router.delete(
    "/projects/{project_id}/daily-reports/{report_id}/photos/uploads/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_dpr_photo_upload(
    project_id: UUID,
    report_id: UUID,
    upload_id: UUID,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Response:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    _require_permission(context, project_id, "files.file.upload")
    await _require_existing_draft(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    upload = await db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == context.organization_id,
            UploadSession.user_id == session.user_id,
        )
        .with_for_update()
    )
    if upload is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if upload.status == UploadStatus.FINALIZED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Finalized photo upload cannot be cancelled")

    try:
        provider = configured_storage_provider()
        if upload.provider_key == provider.provider_key:
            await provider.delete_object(upload.temporary_storage_key)
        reserved = upload.reserved_bytes
        if reserved > 0:
            await release_storage_reservation(
                db,
                organization_id=context.organization_id,
                size_bytes=reserved,
            )
        upload.reserved_bytes = 0
        upload.status = UploadStatus.FAILED
        upload.failure_reason = "cancelled_by_user"
        await db.commit()
    except Exception as exc:
        await db.rollback()
        _domain_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/projects/{project_id}/daily-reports/{report_id}/photos/{asset_id}",
    response_model=DPRPhotoChangeRead,
)
async def delete_dpr_photo(
    project_id: UUID,
    report_id: UUID,
    asset_id: UUID,
    expected_revision: int = Query(ge=1),
    db: DbSession = None,
    session: CurrentSession = None,
    _csrf: CsrfProtected = None,
) -> DPRPhotoChangeRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    try:
        report = await remove_dpr_photo(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            membership_id=context.membership_id,
            asset_id=asset_id,
            expected_revision=expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        _domain_error(exc)
    return DPRPhotoChangeRead(report_revision=report.revision)
