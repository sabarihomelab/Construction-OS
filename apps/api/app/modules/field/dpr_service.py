from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQ, BOQItem, BOQStatus, RecordStatus, WBSCode
from app.modules.events.service import enqueue_event
from app.modules.field.dpr_models import DPRWorkProgressEntry
from app.modules.field.dpr_schemas import DPRWorkProgressWrite
from app.modules.field.models import (
    DailyReport,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportStatus,
)
from app.modules.search.service import schedule_search_index


class DPRValidationError(ValueError):
    pass


class DPRConflictError(ValueError):
    pass


async def _load_draft_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
) -> DailyReport:
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
        raise DPRValidationError("Daily Progress Report was not found")
    if report.revision != expected_revision:
        raise DPRConflictError(
            f"DPR changed from revision {expected_revision} to {report.revision}; refresh before saving"
        )
    if report.status not in {DailyReportStatus.DRAFT, DailyReportStatus.REJECTED}:
        raise DPRValidationError("Only draft/rejected DPR work progress can be edited")
    return report


async def _validate_progress_row(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    row: DPRWorkProgressWrite,
) -> None:
    if row.wbs_code_id is not None:
        wbs = await db.scalar(
            select(WBSCode).where(
                WBSCode.id == row.wbs_code_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
                WBSCode.status == RecordStatus.ACTIVE,
            )
        )
        if wbs is None:
            raise DPRValidationError("Work progress WBS / Cost Code is not active in this project")
    if row.boq_item_id is not None:
        result = await db.execute(
            select(BOQItem, BOQ)
            .join(BOQ, BOQ.id == BOQItem.boq_id)
            .where(
                BOQItem.id == row.boq_item_id,
                BOQItem.organization_id == organization_id,
                BOQItem.project_id == project_id,
                BOQ.organization_id == organization_id,
                BOQ.project_id == project_id,
                BOQ.status == BOQStatus.APPROVED,
            )
        )
        match = result.first()
        if match is None:
            raise DPRValidationError("Work progress BOQ Item must belong to an approved project BOQ")
        boq_item, _boq = match
        if row.wbs_code_id is not None and boq_item.wbs_code_id not in {None, row.wbs_code_id}:
            raise DPRValidationError("Work progress WBS does not match the selected BOQ Item")


async def list_work_progress(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> list[DPRWorkProgressEntry]:
    rows = await db.scalars(
        select(DPRWorkProgressEntry)
        .where(
            DPRWorkProgressEntry.organization_id == organization_id,
            DPRWorkProgressEntry.project_id == project_id,
            DPRWorkProgressEntry.daily_report_id == report_id,
        )
        .order_by(DPRWorkProgressEntry.created_at, DPRWorkProgressEntry.id)
    )
    return list(rows.all())


async def replace_work_progress(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    rows: Sequence[DPRWorkProgressWrite],
    actor_user_id: UUID,
    session_id: UUID | None,
    reason: str | None,
) -> DailyReport:
    report = await _load_draft_report(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    for row in rows:
        await _validate_progress_row(
            db,
            organization_id=organization_id,
            project_id=project_id,
            row=row,
        )
    await db.execute(
        delete(DPRWorkProgressEntry).where(
            DPRWorkProgressEntry.organization_id == organization_id,
            DPRWorkProgressEntry.project_id == project_id,
            DPRWorkProgressEntry.daily_report_id == report_id,
        )
    )
    for row in rows:
        db.add(
            DPRWorkProgressEntry(
                organization_id=organization_id,
                project_id=project_id,
                daily_report_id=report_id,
                **row.model_dump(),
            )
        )
    report.revision += 1
    db.add(
        DailyReportHistoryEvent(
            organization_id=organization_id,
            daily_report_id=report.id,
            event_type=DailyReportHistoryType.UPDATED,
            report_revision=report.revision,
            actor_user_id=actor_user_id,
            details={"section": "work_progress", "row_count": len(rows), "reason": reason},
        )
    )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="dpr.work_progress.replaced",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"revision": report.revision, "row_count": len(rows)},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="daily_report.updated",
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
        required_permission_key="field.daily_report.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": report.revision, "section": "work_progress"},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
    )
    return report
