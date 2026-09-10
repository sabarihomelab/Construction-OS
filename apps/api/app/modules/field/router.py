from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field.models import (
    DailyReport,
    DailyReportCrewEntry,
    DailyReportDelayEntry,
    DailyReportDeliveryEntry,
    DailyReportEquipmentEntry,
    DailyReportHistoryEvent,
    DailyReportProductionEntry,
    DailyReportSafetyEntry,
    DailyReportWorkEntry,
)
from app.modules.field.schemas import (
    CrewEntryRead,
    DailyReportCreate,
    DailyReportDetailRead,
    DailyReportHistoryRead,
    DailyReportRead,
    DailyReportReject,
    DailyReportSectionsWrite,
    DailyReportUpdate,
    DailyReportVersionAction,
    DelayEntryRead,
    DeliveryEntryRead,
    EquipmentEntryRead,
    ProductionEntryRead,
    SafetyEntryRead,
    WorkEntryRead,
)
from app.modules.field.service import (
    DailyReportConflictError,
    DailyReportValidationError,
    approve_daily_report,
    create_daily_report,
    reject_daily_report,
    reopen_daily_report,
    replace_daily_report_sections,
    submit_daily_report,
    update_daily_report,
    void_daily_report,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(prefix="/projects/{project_id}/daily-reports", tags=["daily-reports"])


def _require_permission(context, project_id: UUID, permission_key: str) -> None:
    project_permissions = {
        key: set(values) for key, values in context.project_permissions.items()
    }
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, DailyReportConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _load_report_or_404(
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
    return report


async def _detail(db: DbSession, report: DailyReport) -> DailyReportDetailRead:
    async def rows(model):
        result = await db.scalars(
            select(model)
            .where(
                model.organization_id == report.organization_id,
                model.daily_report_id == report.id,
            )
            .order_by(model.created_at, model.id)
        )
        return list(result.all())

    base = DailyReportRead.model_validate(report).model_dump()
    return DailyReportDetailRead(
        **base,
        crew=[CrewEntryRead.model_validate(item) for item in await rows(DailyReportCrewEntry)],
        work=[WorkEntryRead.model_validate(item) for item in await rows(DailyReportWorkEntry)],
        equipment=[
            EquipmentEntryRead.model_validate(item)
            for item in await rows(DailyReportEquipmentEntry)
        ],
        deliveries=[
            DeliveryEntryRead.model_validate(item)
            for item in await rows(DailyReportDeliveryEntry)
        ],
        production=[
            ProductionEntryRead.model_validate(item)
            for item in await rows(DailyReportProductionEntry)
        ],
        delays=[DelayEntryRead.model_validate(item) for item in await rows(DailyReportDelayEntry)],
        safety=[SafetyEntryRead.model_validate(item) for item in await rows(DailyReportSafetyEntry)],
    )


@router.get("", response_model=list[DailyReportRead])
async def list_daily_reports(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[DailyReport]:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    reports = await db.scalars(
        select(DailyReport)
        .where(
            DailyReport.organization_id == context.organization_id,
            DailyReport.project_id == project_id,
        )
        .order_by(DailyReport.report_date.desc(), DailyReport.shift_code, DailyReport.id)
    )
    return list(reports.all())


@router.post("", response_model=DailyReportRead, status_code=status.HTTP_201_CREATED)
async def create_daily_report_route(
    project_id: UUID,
    payload: DailyReportCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.create")
    try:
        report = await create_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{report_id}", response_model=DailyReportDetailRead)
async def get_daily_report(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DailyReportDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    report = await _load_report_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    return await _detail(db, report)


@router.patch("/{report_id}", response_model=DailyReportRead)
async def patch_daily_report(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    try:
        report = await update_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(
                exclude={"expected_revision", "reason"},
                exclude_unset=True,
            ),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.put("/{report_id}/sections", response_model=DailyReportDetailRead)
async def replace_sections(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportSectionsWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReportDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    sections = payload.model_dump(
        exclude={"expected_revision", "reason"},
        exclude_unset=True,
    )
    try:
        report = await replace_daily_report_sections(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            sections=sections,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return await _detail(db, report)
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{report_id}/submit", response_model=DailyReportRead)
async def submit_report(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.submit")
    try:
        report = await submit_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{report_id}/approve", response_model=DailyReportRead)
async def approve_report(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.approve")
    try:
        report = await approve_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{report_id}/reject", response_model=DailyReportRead)
async def reject_report(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportReject,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.approve")
    try:
        report = await reject_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{report_id}/reopen", response_model=DailyReportRead)
async def reopen_report(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.update")
    try:
        report = await reopen_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{report_id}/void", response_model=DailyReportRead)
async def void_report(
    project_id: UUID,
    report_id: UUID,
    payload: DailyReportReject,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DailyReport:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.manage")
    try:
        report = await void_daily_report(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            report_id=report_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(report)
        return report
    except (DailyReportConflictError, DailyReportValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{report_id}/history", response_model=list[DailyReportHistoryRead])
async def get_daily_report_history(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[DailyReportHistoryEvent]:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, "field.daily_report.view")
    await _load_report_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    rows = await db.scalars(
        select(DailyReportHistoryEvent)
        .where(
            DailyReportHistoryEvent.organization_id == context.organization_id,
            DailyReportHistoryEvent.daily_report_id == report_id,
        )
        .order_by(DailyReportHistoryEvent.created_at, DailyReportHistoryEvent.id)
    )
    return list(rows.all())
