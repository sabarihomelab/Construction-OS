from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.workforce.attendance_models import (
    AttendanceEntry,
    AttendanceHistoryEvent,
    AttendanceRegister,
)
from app.modules.workforce.attendance_schemas import (
    AttendanceDPRSummaryRead,
    AttendanceDPRSummaryRow,
    AttendanceEntriesWrite,
    AttendanceEntryRead,
    AttendanceHistoryRead,
    AttendanceRegisterCreate,
    AttendanceRegisterDetailRead,
    AttendanceRegisterRead,
    AttendanceReject,
    AttendanceVersionAction,
)
from app.modules.workforce.attendance_service import (
    build_dpr_summary,
    create_attendance_register,
    replace_attendance_entries,
    review_attendance,
    submit_attendance,
)
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError

router = APIRouter(tags=["workforce-attendance"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> set[str]:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    permissions = set(context.permissions)
    permissions.update(scoped.get(str(project_id), set()))
    return permissions


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, WorkforceConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _detail(db: DbSession, register: AttendanceRegister) -> AttendanceRegisterDetailRead:
    entries = list(
        (
            await db.scalars(
                select(AttendanceEntry)
                .where(
                    AttendanceEntry.organization_id == register.organization_id,
                    AttendanceEntry.register_id == register.id,
                )
                .order_by(AttendanceEntry.trade, AttendanceEntry.worker_id)
            )
        ).all()
    )
    return AttendanceRegisterDetailRead(
        **AttendanceRegisterRead.model_validate(register).model_dump(),
        entries=[AttendanceEntryRead.model_validate(entry) for entry in entries],
    )


@router.get(
    "/projects/{project_id}/workforce/attendance",
    response_model=list[AttendanceRegisterRead],
)
async def list_attendance_registers(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[AttendanceRegister]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.attendance.view")
    rows = await db.scalars(
        select(AttendanceRegister)
        .where(
            AttendanceRegister.organization_id == context.organization_id,
            AttendanceRegister.project_id == project_id,
        )
        .order_by(AttendanceRegister.attendance_date.desc(), AttendanceRegister.shift_code)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/workforce/attendance",
    response_model=AttendanceRegisterDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attendance_register_route(
    project_id: UUID,
    payload: AttendanceRegisterCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AttendanceRegisterDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.attendance.create")
    try:
        register = await create_attendance_register(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            attendance_date=payload.attendance_date,
            shift_code=payload.shift_code,
            notes=payload.notes,
            populate_active_workers=payload.populate_active_workers,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(register)
        return await _detail(db, register)
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/workforce/attendance/{register_id}",
    response_model=AttendanceRegisterDetailRead,
)
async def get_attendance_register(
    project_id: UUID,
    register_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> AttendanceRegisterDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.attendance.view")
    register = await db.scalar(
        select(AttendanceRegister).where(
            AttendanceRegister.id == register_id,
            AttendanceRegister.organization_id == context.organization_id,
            AttendanceRegister.project_id == project_id,
        )
    )
    if register is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance register not found")
    return await _detail(db, register)


@router.put(
    "/projects/{project_id}/workforce/attendance/{register_id}/entries",
    response_model=AttendanceRegisterDetailRead,
)
async def replace_attendance_entries_route(
    project_id: UUID,
    register_id: UUID,
    payload: AttendanceEntriesWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AttendanceRegisterDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.attendance.update")
    try:
        register = await replace_attendance_entries(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            register_id=register_id,
            expected_revision=payload.expected_revision,
            entries=[entry.model_dump() for entry in payload.entries],
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(register)
        return await _detail(db, register)
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/workforce/attendance/{register_id}/submit",
    response_model=AttendanceRegisterRead,
)
async def submit_attendance_route(
    project_id: UUID,
    register_id: UUID,
    payload: AttendanceVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AttendanceRegister:
    context = await build_access_context(db, session.membership_id)
    permissions = _require_project_permission(context, project_id, "workforce.attendance.submit")
    try:
        register = await submit_attendance(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            register_id=register_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            permission_keys=permissions,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(register)
        return register
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/workforce/attendance/{register_id}/approve",
    response_model=AttendanceRegisterRead,
)
async def approve_attendance_route(
    project_id: UUID,
    register_id: UUID,
    payload: AttendanceVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AttendanceRegister:
    context = await build_access_context(db, session.membership_id)
    permissions = _require_project_permission(context, project_id, "workforce.attendance.approve")
    try:
        register = await review_attendance(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            register_id=register_id,
            expected_revision=payload.expected_revision,
            approve=True,
            actor_user_id=session.user_id,
            permission_keys=permissions,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(register)
        return register
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/workforce/attendance/{register_id}/reject",
    response_model=AttendanceRegisterRead,
)
async def reject_attendance_route(
    project_id: UUID,
    register_id: UUID,
    payload: AttendanceReject,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AttendanceRegister:
    context = await build_access_context(db, session.membership_id)
    permissions = _require_project_permission(context, project_id, "workforce.attendance.approve")
    try:
        register = await review_attendance(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            register_id=register_id,
            expected_revision=payload.expected_revision,
            approve=False,
            actor_user_id=session.user_id,
            permission_keys=permissions,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(register)
        return register
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/workforce/attendance/{register_id}/history",
    response_model=list[AttendanceHistoryRead],
)
async def list_attendance_history(
    project_id: UUID,
    register_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[AttendanceHistoryEvent]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.attendance.view")
    register = await db.scalar(
        select(AttendanceRegister.id).where(
            AttendanceRegister.id == register_id,
            AttendanceRegister.organization_id == context.organization_id,
            AttendanceRegister.project_id == project_id,
        )
    )
    if register is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance register not found")
    rows = await db.scalars(
        select(AttendanceHistoryEvent)
        .where(
            AttendanceHistoryEvent.organization_id == context.organization_id,
            AttendanceHistoryEvent.register_id == register_id,
        )
        .order_by(AttendanceHistoryEvent.created_at)
    )
    return list(rows.all())


@router.get(
    "/projects/{project_id}/workforce/attendance/{register_id}/dpr-summary",
    response_model=AttendanceDPRSummaryRead,
)
async def attendance_dpr_summary(
    project_id: UUID,
    register_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> AttendanceDPRSummaryRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.attendance.view")
    register = await db.scalar(
        select(AttendanceRegister).where(
            AttendanceRegister.id == register_id,
            AttendanceRegister.organization_id == context.organization_id,
            AttendanceRegister.project_id == project_id,
        )
    )
    if register is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance register not found")
    try:
        rows = await build_dpr_summary(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            register_id=register_id,
        )
        return AttendanceDPRSummaryRead(
            register_id=register.id,
            project_id=project_id,
            attendance_date=register.attendance_date,
            shift_code=register.shift_code,
            rows=[AttendanceDPRSummaryRow.model_validate(row) for row in rows],
        )
    except WorkforceValidationError as exc:
        _domain_error(exc)
