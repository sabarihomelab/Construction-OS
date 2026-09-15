from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.workforce.attendance_admin_schemas import AttendanceReopenRequest
from app.modules.workforce.attendance_admin_service import reopen_attendance
from app.modules.workforce.attendance_models import AttendanceRegister
from app.modules.workforce.attendance_schemas import AttendanceRegisterRead
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError

router = APIRouter(tags=["workforce-attendance-admin"])


def _require_reopen_permission(context, project_id: UUID) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        "workforce.attendance.reopen",
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.post(
    "/projects/{project_id}/workforce/attendance/{register_id}/reopen",
    response_model=AttendanceRegisterRead,
)
async def reopen_attendance_route(
    project_id: UUID,
    register_id: UUID,
    payload: AttendanceReopenRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AttendanceRegister:
    context = await build_access_context(db, session.membership_id)
    _require_reopen_permission(context, project_id)
    try:
        register = await reopen_attendance(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            register_id=register_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(register)
        return register
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        if isinstance(exc, WorkforceConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
