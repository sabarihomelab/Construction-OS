from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.events.service import enqueue_event
from app.modules.field.models import (
    DailyReport,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportStatus,
)
from app.modules.files.models import FileAsset, FileLink, FileSourceType, FileVersion, UploadSession
from app.modules.files.service import finalize_upload
from app.modules.files.storage import StorageProvider
from app.modules.search.service import schedule_search_index


class DPRPhotoValidationError(ValueError):
    pass


class DPRPhotoConflictError(ValueError):
    pass


PHOTO_SOURCE_SYSTEM = "dpr-photo-upload"


async def require_photo_section_enabled(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    project_id: UUID,
) -> None:
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="field",
        project_id=project_id,
    )
    enabled: object = ["crew", "work", "photos", "notes"]
    for setting in config.settings:
        if setting.key == "field.daily_reports.sections.enabled":
            enabled = setting.value
            break
    if not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
        raise DPRPhotoValidationError("Daily Report section configuration is invalid")
    if "photos" not in enabled:
        raise DPRPhotoValidationError("Photos are disabled for this project")


async def require_draft_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    lock: bool = False,
) -> DailyReport:
    query = select(DailyReport).where(
        DailyReport.id == report_id,
        DailyReport.organization_id == organization_id,
        DailyReport.project_id == project_id,
    )
    if lock:
        query = query.with_for_update()
    report = await db.scalar(query)
    if report is None:
        raise DPRPhotoValidationError("Daily Report was not found")
    if report.status != DailyReportStatus.DRAFT:
        raise DPRPhotoValidationError("Photos can only be changed while the Daily Report is a draft")
    if report.revision != expected_revision:
        raise DPRPhotoConflictError(
            f"Daily Report changed from revision {expected_revision} to {report.revision}; refresh before changing photos"
        )
    return report


async def list_dpr_photos(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> tuple[DailyReport, list[dict[str, object]]]:
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        raise DPRPhotoValidationError("Daily Report was not found")

    rows = await db.execute(
        select(FileLink, FileAsset, FileVersion)
        .join(
            FileAsset,
            (FileAsset.id == FileLink.asset_id)
            & (FileAsset.organization_id == FileLink.organization_id),
        )
        .join(
            FileVersion,
            (FileVersion.asset_id == FileLink.asset_id)
            & (FileVersion.organization_id == FileLink.organization_id)
            & (FileVersion.version == FileLink.pinned_version),
        )
        .where(
            FileLink.organization_id == organization_id,
            FileLink.entity_type == "daily_report",
            FileLink.entity_id == report_id,
            FileLink.relation_type == "photo",
        )
        .order_by(FileLink.created_at, FileLink.id)
    )
    result: list[dict[str, object]] = []
    for link, _asset, version in rows.all():
        metadata = version.source_metadata or {}
        result.append(
            {
                "asset_id": link.asset_id,
                "version": version.version,
                "filename": version.original_filename,
                "content_type": version.detected_content_type or version.declared_content_type,
                "size_bytes": version.size_bytes,
                "relation_type": link.relation_type,
                "client_photo_id": metadata.get("client_photo_id"),
                "caption": metadata.get("caption"),
                "captured_at": metadata.get("captured_at"),
                "created_at": link.created_at,
                "report_revision": report.revision,
            }
        )
    return report, result


async def _published_photo_change(
    db: AsyncSession,
    *,
    report: DailyReport,
    actor_user_id: UUID,
    session_id: UUID | None,
    action: str,
    asset_id: UUID,
) -> None:
    db.add(
        DailyReportHistoryEvent(
            organization_id=report.organization_id,
            daily_report_id=report.id,
            event_type=DailyReportHistoryType.UPDATED,
            report_revision=report.revision,
            actor_user_id=actor_user_id,
            details={"section": "photos", "action": action, "asset_id": str(asset_id)},
        )
    )
    await record_audit_event(
        db,
        organization_id=report.organization_id,
        action=f"daily_report.photo.{action}",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"asset_id": str(asset_id), "revision": report.revision},
    )
    await enqueue_event(
        db,
        organization_id=report.organization_id,
        event_type="daily_report.updated",
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
        required_permission_key="field.daily_report.view",
        scope_type="project",
        scope_id=report.project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": report.revision, "status": report.status.value, "section": "photos"},
    )
    await schedule_search_index(
        db,
        organization_id=report.organization_id,
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
    )


async def finalize_dpr_photo(
    db: AsyncSession,
    *,
    provider: StorageProvider,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    membership_id: UUID,
    upload_id: UUID,
    expected_revision: int,
    client_photo_id: UUID,
    caption: str | None,
    captured_at: datetime | None,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> tuple[DailyReport, FileLink, FileVersion]:
    await require_photo_section_enabled(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )

    report = await db.scalar(
        select(DailyReport)
        .where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
        .with_for_update()
    )
    if report is None:
        raise DPRPhotoValidationError("Daily Report was not found")

    existing_version = await db.scalar(
        select(FileVersion).where(
            FileVersion.organization_id == organization_id,
            FileVersion.source_system == PHOTO_SOURCE_SYSTEM,
            FileVersion.external_id == str(upload_id),
        )
    )
    if existing_version is not None:
        existing_link = await db.scalar(
            select(FileLink).where(
                FileLink.organization_id == organization_id,
                FileLink.entity_type == "daily_report",
                FileLink.entity_id == report_id,
                FileLink.asset_id == existing_version.asset_id,
                FileLink.relation_type == "photo",
            )
        )
        if existing_link is not None:
            return report, existing_link, existing_version

    if report.status != DailyReportStatus.DRAFT:
        raise DPRPhotoValidationError("Photos can only be changed while the Daily Report is a draft")
    if report.revision != expected_revision:
        raise DPRPhotoConflictError(
            f"Daily Report changed from revision {expected_revision} to {report.revision}; refresh before changing photos"
        )

    upload = await db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == organization_id,
            UploadSession.user_id == actor_user_id,
        )
        .with_for_update()
    )
    if upload is None:
        raise DPRPhotoValidationError("Photo upload session was not found")

    metadata = {
        "project_id": str(project_id),
        "report_id": str(report_id),
        "client_photo_id": str(client_photo_id),
        "caption": caption.strip() if caption and caption.strip() else None,
        "captured_at": captured_at.isoformat() if captured_at else None,
    }
    if upload.status.value == "finalized" and existing_version is None:
        raise DPRPhotoValidationError("Finalized photo upload could not be reconciled")

    asset, version = await finalize_upload(
        db,
        provider=provider,
        upload_id=upload_id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        asset_name=upload.original_filename,
        source_type=FileSourceType.USER,
        source_system=PHOTO_SOURCE_SYSTEM,
        external_id=str(upload_id),
        external_version=str(client_photo_id),
        session_id=session_id,
    )
    version.source_metadata = metadata

    link = FileLink(
        organization_id=organization_id,
        entity_type="daily_report",
        entity_id=report_id,
        asset_id=asset.id,
        relation_type="photo",
        pinned_version=version.version,
        created_by_user_id=actor_user_id,
    )
    db.add(link)
    report.revision += 1
    await db.flush()
    await _published_photo_change(
        db,
        report=report,
        actor_user_id=actor_user_id,
        session_id=session_id,
        action="added",
        asset_id=asset.id,
    )
    return report, link, version


async def remove_dpr_photo(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    membership_id: UUID,
    asset_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> DailyReport:
    await require_photo_section_enabled(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    report = await require_draft_report(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
        lock=True,
    )
    link = await db.scalar(
        select(FileLink).where(
            FileLink.organization_id == organization_id,
            FileLink.entity_type == "daily_report",
            FileLink.entity_id == report_id,
            FileLink.asset_id == asset_id,
            FileLink.relation_type == "photo",
        )
    )
    if link is None:
        raise DPRPhotoValidationError("DPR photo was not found")

    await db.execute(delete(FileLink).where(FileLink.id == link.id))
    report.revision += 1
    await db.flush()
    await _published_photo_change(
        db,
        report=report,
        actor_user_id=actor_user_id,
        session_id=session_id,
        action="removed",
        asset_id=asset_id,
    )
    return report
