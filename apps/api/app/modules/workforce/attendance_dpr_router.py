from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession
from app.modules.workforce.attendance_models import AttendanceRegister, AttendanceRegisterStatus
from app.modules.workforce.attendance_schemas import AttendanceDPRSummaryRead, AttendanceDPRSummaryRow
from app.modules.workforce.attendance_service import build_dpr_summary
from app.modules.workforce.service import WorkforceValidationError

router = APIRouter(tags=["workforce-attendance"])


def _require_attendance_view(context, project_id: UUID) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if project_permission_is_allowed(
        "workforce.attendance.view",
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/workforce/attendance/dpr-summary",
    response_model=AttendanceDPRSummaryRead,
)
async def approved_attendance_dpr_summary(
    project_id: UUID,
    attendance_date: date,
    db: DbSession,
    session: CurrentSession,
    shift_code: str = Query(default="day", min_length=1, max_length=40),
) -> AttendanceDPRSummaryRead:
    context = await build_access_context(db, session.membership_id)
    _require_attendance_view(context, project_id)

    register = await db.scalar(
        select(AttendanceRegister).where(
            AttendanceRegister.organization_id == context.organization_id,
            AttendanceRegister.project_id == project_id,
            AttendanceRegister.attendance_date == attendance_date,
            AttendanceRegister.shift_code == shift_code,
            AttendanceRegister.status == AttendanceRegisterStatus.APPROVED,
        )
    )
    if register is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved attendance register not found",
        )

    try:
        rows = await build_dpr_summary(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            register_id=register.id,
        )
    except WorkforceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return AttendanceDPRSummaryRead(
        register_id=register.id,
        project_id=project_id,
        attendance_date=register.attendance_date,
        shift_code=register.shift_code,
        rows=[AttendanceDPRSummaryRow.model_validate(row) for row in rows],
    )
