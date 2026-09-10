from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.workforce.management import (
    end_crew_membership,
    update_crew,
    update_project_worker_assignment,
)
from app.modules.workforce.models import Crew, CrewMembership, ProjectWorkerAssignment
from app.modules.workforce.schemas import (
    CrewMembershipEnd,
    CrewMembershipRead,
    CrewRead,
    CrewUpdate,
    ProjectWorkerAssignmentRead,
    ProjectWorkerAssignmentUpdate,
)
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError

router = APIRouter(tags=["workforce"])


def _require_org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, WorkforceConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/workforce/crews/{crew_id}", response_model=CrewRead)
async def update_crew_route(
    crew_id: UUID,
    payload: CrewUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Crew:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.crew.manage")
    try:
        crew = await update_crew(
            db,
            organization_id=context.organization_id,
            crew_id=crew_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(
                exclude={"expected_revision", "reason"}, exclude_unset=True
            ),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(crew)
        return crew
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/workforce/crews/{crew_id}/memberships/{crew_membership_id}/end",
    response_model=CrewMembershipRead,
)
async def end_crew_membership_route(
    crew_id: UUID,
    crew_membership_id: UUID,
    payload: CrewMembershipEnd,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> CrewMembership:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.crew.manage")
    try:
        membership = await end_crew_membership(
            db,
            organization_id=context.organization_id,
            crew_id=crew_id,
            crew_membership_id=crew_membership_id,
            expected_revision=payload.expected_revision,
            effective_to=payload.effective_to,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(membership)
        return membership
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.patch(
    "/projects/{project_id}/workforce/assignments/{assignment_id}",
    response_model=ProjectWorkerAssignmentRead,
)
async def update_project_worker_assignment_route(
    project_id: UUID,
    assignment_id: UUID,
    payload: ProjectWorkerAssignmentUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectWorkerAssignment:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.assignment.manage")
    try:
        assignment = await update_project_worker_assignment(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(
                exclude={"expected_revision", "reason"}, exclude_unset=True
            ),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(assignment)
        return assignment
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)
