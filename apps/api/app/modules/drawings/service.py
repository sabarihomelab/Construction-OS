from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.documents.models import DocumentRevision
from app.modules.drawings.measurement_engine import calculate_measurement, calibration_scale
from app.modules.drawings.models import (
    DrawingCalibration,
    DrawingComparison,
    DrawingComparisonStatus,
    DrawingMeasurement,
    DrawingMeasurementType,
    DrawingPin,
    DrawingPinType,
    DrawingRenderPackage,
    DrawingRevision,
    DrawingRevisionStatus,
    DrawingSet,
    DrawingSheet,
)
from app.modules.events.service import enqueue_event
from app.modules.files.models import FileProcessingStatus, FileScanStatus, FileVersion
from app.modules.jobs.service import enqueue_job
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index


class DrawingValidationError(ValueError):
    pass


class DrawingConflictError(ValueError):
    pass


async def create_drawing_set(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    name: str,
    actor_user_id: UUID,
    description: str | None = None,
) -> DrawingSet:
    project = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise DrawingValidationError("Project was not found")
    normalized_name = name.strip()
    if not normalized_name:
        raise DrawingValidationError("Drawing set name is required")
    existing = await db.scalar(
        select(DrawingSet.id).where(
            DrawingSet.project_id == project_id,
            DrawingSet.name == normalized_name,
        )
    )
    if existing is not None:
        raise DrawingConflictError("Drawing set name already exists in this project")
    drawing_set = DrawingSet(
        organization_id=organization_id,
        project_id=project_id,
        name=normalized_name,
        description=description,
    )
    db.add(drawing_set)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="drawing_set.created",
        target_type="drawing_set",
        target_id=str(drawing_set.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "name": normalized_name},
    )
    return drawing_set


async def create_sheet(
    db: AsyncSession,
    *,
    organization_id: UUID,
    drawing_set_id: UUID,
    sheet_number: str,
    title: str,
    discipline_code: str | None = None,
) -> DrawingSheet:
    drawing_set = await db.scalar(
        select(DrawingSet).where(
            DrawingSet.id == drawing_set_id,
            DrawingSet.organization_id == organization_id,
        )
    )
    if drawing_set is None:
        raise DrawingValidationError("Drawing set was not found")
    number = sheet_number.strip()
    normalized_title = title.strip()
    if not number or not normalized_title:
        raise DrawingValidationError("Sheet number and title are required")
    existing = await db.scalar(
        select(DrawingSheet.id).where(
            DrawingSheet.drawing_set_id == drawing_set_id,
            DrawingSheet.sheet_number == number,
        )
    )
    if existing is not None:
        raise DrawingConflictError("Sheet number already exists in this drawing set")
    sheet = DrawingSheet(
        organization_id=organization_id,
        drawing_set_id=drawing_set_id,
        sheet_number=number,
        title=normalized_title,
        discipline_code=discipline_code.strip() if discipline_code else None,
    )
    db.add(sheet)
    drawing_set.version += 1
    await db.flush()
    return sheet


async def add_drawing_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    sheet_id: UUID,
    revision_label: str,
    file_version_id: UUID,
    actor_user_id: UUID,
    source_page: int = 1,
    document_revision_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> DrawingRevision:
    if source_page < 1:
        raise DrawingValidationError("Drawing source page must be at least 1")
    sheet = await db.scalar(
        select(DrawingSheet)
        .where(DrawingSheet.id == sheet_id, DrawingSheet.organization_id == organization_id)
        .with_for_update()
    )
    if sheet is None:
        raise DrawingValidationError("Drawing sheet was not found")
    file_version = await db.scalar(
        select(FileVersion).where(
            FileVersion.id == file_version_id,
            FileVersion.organization_id == organization_id,
        )
    )
    if file_version is None:
        raise DrawingValidationError("Drawing file version was not found")
    if document_revision_id is not None:
        document_revision = await db.scalar(
            select(DocumentRevision).where(
                DocumentRevision.id == document_revision_id,
                DocumentRevision.organization_id == organization_id,
            )
        )
        if document_revision is None or document_revision.file_version_id != file_version_id:
            raise DrawingValidationError("Document revision must reference the same file version")

    label = revision_label.strip()
    if not label:
        raise DrawingValidationError("Drawing revision label is required")
    duplicate = await db.scalar(
        select(DrawingRevision.id).where(
            DrawingRevision.sheet_id == sheet_id,
            DrawingRevision.revision_label == label,
        )
    )
    if duplicate is not None:
        raise DrawingConflictError("Drawing revision label already exists for this sheet")

    sequence = sheet.current_revision_sequence + 1
    revision = DrawingRevision(
        organization_id=organization_id,
        sheet_id=sheet_id,
        sequence=sequence,
        revision_label=label,
        file_version_id=file_version_id,
        document_revision_id=document_revision_id,
        source_page=source_page,
        created_by_user_id=actor_user_id,
    )
    db.add(revision)
    sheet.current_revision_sequence = sequence
    sheet.version += 1
    await db.flush()

    if (
        file_version.scan_status == FileScanStatus.CLEAN
        and file_version.processing_status == FileProcessingStatus.READY
    ):
        revision.status = DrawingRevisionStatus.PROCESSING
        await enqueue_job(
            db,
            organization_id=organization_id,
            job_type="drawings.process_revision",
            idempotency_key=f"drawing-process:{revision.id}:render:{revision.render_version}",
            payload={"drawing_revision_id": str(revision.id), "render_version": revision.render_version},
            created_by_user_id=actor_user_id,
            correlation_id=correlation_id,
        )
    await db.flush()
    return revision


async def publish_drawing_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    revision_id: UUID,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> DrawingRevision:
    revision = await db.scalar(
        select(DrawingRevision)
        .where(
            DrawingRevision.id == revision_id,
            DrawingRevision.organization_id == organization_id,
        )
        .with_for_update()
    )
    if revision is None:
        raise DrawingValidationError("Drawing revision was not found")
    if revision.status != DrawingRevisionStatus.READY:
        raise DrawingConflictError("Drawing revision must be render-ready before publishing")

    render_ready = await db.scalar(
        select(func.count())
        .select_from(DrawingRenderPackage)
        .where(
            DrawingRenderPackage.drawing_revision_id == revision.id,
            DrawingRenderPackage.render_version == revision.render_version,
            DrawingRenderPackage.completed_at.is_not(None),
        )
    )
    if not render_ready:
        raise DrawingConflictError("Drawing render package is not ready")

    sheet = await db.scalar(
        select(DrawingSheet)
        .where(
            DrawingSheet.id == revision.sheet_id,
            DrawingSheet.organization_id == organization_id,
        )
        .with_for_update()
    )
    if sheet is None:
        raise DrawingValidationError("Drawing sheet was not found")
    previous_rows = await db.scalars(
        select(DrawingRevision).where(
            DrawingRevision.sheet_id == sheet.id,
            DrawingRevision.status == DrawingRevisionStatus.PUBLISHED,
        )
    )
    for previous in previous_rows.all():
        previous.status = DrawingRevisionStatus.SUPERSEDED

    revision.status = DrawingRevisionStatus.PUBLISHED
    revision.published_at = datetime.now(UTC)
    sheet.version += 1
    drawing_set = await db.scalar(
        select(DrawingSet).where(
            DrawingSet.id == sheet.drawing_set_id,
            DrawingSet.organization_id == organization_id,
        )
    )
    if drawing_set is None:
        raise DrawingValidationError("Drawing set was not found")
    drawing_set.version += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="drawing.revision.published",
        target_type="drawing_revision",
        target_id=str(revision.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        risk=AuditRisk.HIGH,
        changes={"sheet_id": str(sheet.id), "revision_label": revision.revision_label},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="drawing.revision.published",
        entity_type="drawing_sheet",
        entity_id=sheet.id,
        entity_version=sheet.version,
        required_permission_key="drawings.drawing.view",
        scope_type="project",
        scope_id=drawing_set.project_id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        payload={"revision_label": revision.revision_label, "version": sheet.version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="drawing_sheet",
        entity_id=sheet.id,
        entity_version=sheet.version,
        correlation_id=correlation_id,
    )
    return revision


async def create_calibration(
    db: AsyncSession,
    *,
    organization_id: UUID,
    drawing_revision_id: UUID,
    point_a: tuple[Decimal, Decimal],
    point_b: tuple[Decimal, Decimal],
    real_length: Decimal,
    unit_code: str,
    actor_user_id: UUID,
) -> DrawingCalibration:
    revision = await db.scalar(
        select(DrawingRevision.id).where(
            DrawingRevision.id == drawing_revision_id,
            DrawingRevision.organization_id == organization_id,
        )
    )
    if revision is None:
        raise DrawingValidationError("Drawing revision was not found")
    calibration_scale(
        point_a_x=point_a[0],
        point_a_y=point_a[1],
        point_b_x=point_b[0],
        point_b_y=point_b[1],
        real_length=real_length,
    )
    current_version = await db.scalar(
        select(func.max(DrawingCalibration.version)).where(
            DrawingCalibration.drawing_revision_id == drawing_revision_id
        )
    )
    calibration = DrawingCalibration(
        organization_id=organization_id,
        drawing_revision_id=drawing_revision_id,
        version=(current_version or 0) + 1,
        point_a_x=point_a[0],
        point_a_y=point_a[1],
        point_b_x=point_b[0],
        point_b_y=point_b[1],
        real_length=real_length,
        unit_code=unit_code.strip(),
        created_by_user_id=actor_user_id,
    )
    if not calibration.unit_code:
        raise DrawingValidationError("Calibration unit is required")
    db.add(calibration)
    await db.flush()
    return calibration


async def create_measurement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    drawing_revision_id: UUID,
    measurement_type: DrawingMeasurementType,
    geometry: dict[str, object],
    unit_code: str,
    actor_user_id: UUID,
    calibration_id: UUID | None = None,
) -> DrawingMeasurement:
    revision_exists = await db.scalar(
        select(DrawingRevision.id).where(
            DrawingRevision.id == drawing_revision_id,
            DrawingRevision.organization_id == organization_id,
        )
    )
    if revision_exists is None:
        raise DrawingValidationError("Drawing revision was not found")

    scale: Decimal | None = None
    if measurement_type != DrawingMeasurementType.COUNT:
        if calibration_id is None:
            raise DrawingValidationError("Calibrated measurements require a calibration")
        calibration = await db.scalar(
            select(DrawingCalibration).where(
                DrawingCalibration.id == calibration_id,
                DrawingCalibration.organization_id == organization_id,
                DrawingCalibration.drawing_revision_id == drawing_revision_id,
            )
        )
        if calibration is None:
            raise DrawingValidationError("Drawing calibration was not found")
        scale = calibration_scale(
            point_a_x=calibration.point_a_x,
            point_a_y=calibration.point_a_y,
            point_b_x=calibration.point_b_x,
            point_b_y=calibration.point_b_y,
            real_length=calibration.real_length,
        )
    value = calculate_measurement(measurement_type, geometry, scale=scale)
    measurement = DrawingMeasurement(
        organization_id=organization_id,
        drawing_revision_id=drawing_revision_id,
        calibration_id=calibration_id,
        measurement_type=measurement_type,
        geometry=geometry,
        value=value,
        unit_code=unit_code.strip(),
        created_by_user_id=actor_user_id,
    )
    if not measurement.unit_code:
        raise DrawingValidationError("Measurement unit is required")
    db.add(measurement)
    await db.flush()
    return measurement


async def create_pin(
    db: AsyncSession,
    *,
    organization_id: UUID,
    drawing_revision_id: UUID,
    pin_type: DrawingPinType,
    target_entity_type: str,
    target_entity_id: str,
    x: Decimal,
    y: Decimal,
    actor_user_id: UUID,
    label: str | None = None,
) -> DrawingPin:
    if x < 0 or x > 1 or y < 0 or y > 1:
        raise DrawingValidationError("Drawing pin coordinates must be normalized between 0 and 1")
    revision = await db.scalar(
        select(DrawingRevision.id).where(
            DrawingRevision.id == drawing_revision_id,
            DrawingRevision.organization_id == organization_id,
        )
    )
    if revision is None:
        raise DrawingValidationError("Drawing revision was not found")
    pin = DrawingPin(
        organization_id=organization_id,
        drawing_revision_id=drawing_revision_id,
        pin_type=pin_type,
        target_entity_type=target_entity_type.strip(),
        target_entity_id=target_entity_id.strip(),
        x=x,
        y=y,
        label=label,
        created_by_user_id=actor_user_id,
    )
    if not pin.target_entity_type or not pin.target_entity_id:
        raise DrawingValidationError("Drawing pin target identity is required")
    db.add(pin)
    await db.flush()
    return pin


async def request_comparison(
    db: AsyncSession,
    *,
    organization_id: UUID,
    base_revision_id: UUID,
    compare_revision_id: UUID,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> DrawingComparison:
    if base_revision_id == compare_revision_id:
        raise DrawingValidationError("Drawing comparison requires two different revisions")
    revisions = (
        await db.scalars(
            select(DrawingRevision).where(
                DrawingRevision.organization_id == organization_id,
                DrawingRevision.id.in_([base_revision_id, compare_revision_id]),
            )
        )
    ).all()
    if len(revisions) != 2 or revisions[0].sheet_id != revisions[1].sheet_id:
        raise DrawingValidationError("Drawing comparison revisions must belong to the same sheet")

    existing = await db.scalar(
        select(DrawingComparison).where(
            DrawingComparison.base_revision_id == base_revision_id,
            DrawingComparison.compare_revision_id == compare_revision_id,
        )
    )
    if existing is not None:
        return existing
    comparison = DrawingComparison(
        organization_id=organization_id,
        base_revision_id=base_revision_id,
        compare_revision_id=compare_revision_id,
        status=DrawingComparisonStatus.QUEUED,
    )
    db.add(comparison)
    await db.flush()
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="drawings.compare_revisions",
        idempotency_key=f"drawing-compare:{base_revision_id}:{compare_revision_id}",
        payload={
            "comparison_id": str(comparison.id),
            "base_revision_id": str(base_revision_id),
            "compare_revision_id": str(compare_revision_id),
        },
        created_by_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return comparison
