from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.workforce.management import (
    end_crew_membership,
    update_crew,
    update_project_worker_assignment,
)
from app.modules.workforce.models import (
    Crew,
    CrewMembership,
    ProjectWorkerAssignment,
    ProjectWorkerRate,
)
from app.modules.workforce.rates import create_project_worker_rate, end_project_worker_rate
from app.modules.workforce.schemas import (
    CrewMembershipEnd,
    CrewMembershipRead,
    CrewRead,
    CrewUpdate,
    ProjectWorkerAssignmentRead,
    ProjectWorkerAssignmentUpdate,
    ProjectWorkerRateCreate,
    ProjectWorkerRateEnd,
    ProjectWorkerRateRead,
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
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
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
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
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


@router.get(
    "/projects/{project_id}/workforce/assignments/{assignment_id}/rates",
    response_model=list[ProjectWorkerRateRead],
)
async def list_project_worker_rates(
    project_id: UUID,
    assignment_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectWorkerRate]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.rate.view")
    rows = await db.scalars(
        select(ProjectWorkerRate)
        .where(
            ProjectWorkerRate.organization_id == context.organization_id,
            ProjectWorkerRate.project_id == project_id,
            ProjectWorkerRate.assignment_id == assignment_id,
        )
        .order_by(ProjectWorkerRate.effective_from.desc(), ProjectWorkerRate.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/workforce/assignments/{assignment_id}/rates",
    response_model=ProjectWorkerRateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_worker_rate_route(
    project_id: UUID,
    assignment_id: UUID,
    payload: ProjectWorkerRateCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectWorkerRate:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.rate.manage")
    try:
        rate = await create_project_worker_rate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(rate)
        return rate
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/projects/{project_id}/workforce/assignments/{assignment_id}/rates/{rate_id}/end",
    response_model=ProjectWorkerRateRead,
)
async def end_project_worker_rate_route(
    project_id: UUID,
    assignment_id: UUID,
    rate_id: UUID,
    payload: ProjectWorkerRateEnd,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectWorkerRate:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.rate.manage")
    try:
        rate = await end_project_worker_rate(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            rate_id=rate_id,
            expected_revision=payload.expected_revision,
            effective_to=payload.effective_to,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(rate)
        return rate
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)
