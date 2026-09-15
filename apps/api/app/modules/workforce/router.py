from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.workforce.models import (
    Crew,
    CrewMembership,
    ProjectWorkerAssignment,
    Timecard,
    TimecardHistoryEvent,
    TimeEntry,
    Worker,
)
from app.modules.workforce.schemas import (
    CrewCreate,
    CrewMembershipCreate,
    CrewMembershipRead,
    CrewRead,
    ProjectWorkerAssignmentCreate,
    ProjectWorkerAssignmentRead,
    TimeEntryRead,
    TimecardCreate,
    TimecardDetailRead,
    TimecardEntriesWrite,
    TimecardHistoryRead,
    TimecardRead,
    TimecardReject,
    TimecardVersionAction,
    WorkerCreate,
    WorkerRead,
    WorkerUpdate,
)
from app.modules.workforce.service import (
    WorkforceConflictError,
    WorkforceValidationError,
    add_crew_membership,
    assign_worker_to_project,
    create_crew,
    create_timecard,
    create_worker,
    replace_time_entries,
    review_timecard,
    submit_timecard,
    update_worker,
)

router = APIRouter(tags=["workforce"])


def _require_org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


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


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, WorkforceConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/workforce/workers", response_model=list[WorkerRead])
async def list_workers(db: DbSession, session: CurrentSession) -> list[Worker]:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.worker.view")
    rows = await db.scalars(
        select(Worker)
        .where(Worker.organization_id == context.organization_id)
        .order_by(Worker.last_name, Worker.first_name, Worker.worker_number)
    )
    return list(rows.all())


@router.post(
    "/workforce/workers",
    response_model=WorkerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_worker_route(
    payload: WorkerCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Worker:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.worker.manage")
    try:
        worker = await create_worker(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(worker)
        return worker
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.patch("/workforce/workers/{worker_id}", response_model=WorkerRead)
async def update_worker_route(
    worker_id: UUID,
    payload: WorkerUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Worker:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.worker.manage")
    try:
        worker = await update_worker(
            db,
            organization_id=context.organization_id,
            worker_id=worker_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(
                exclude={"expected_revision", "reason"}, exclude_unset=True
            ),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(worker)
        return worker
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/workforce/crews", response_model=list[CrewRead])
async def list_crews(db: DbSession, session: CurrentSession) -> list[Crew]:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.crew.view")
    rows = await db.scalars(
        select(Crew)
        .where(Crew.organization_id == context.organization_id)
        .order_by(Crew.name)
    )
    return list(rows.all())


@router.post(
    "/workforce/crews",
    response_model=CrewRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_crew_route(
    payload: CrewCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Crew:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.crew.manage")
    try:
        crew = await create_crew(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(crew)
        return crew
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/workforce/crews/{crew_id}/memberships",
    response_model=CrewMembershipRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_crew_membership_route(
    crew_id: UUID,
    payload: CrewMembershipCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> CrewMembership:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "workforce.crew.manage")
    try:
        membership = await add_crew_membership(
            db,
            organization_id=context.organization_id,
            crew_id=crew_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(membership)
        return membership
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/workforce/assignments",
    response_model=list[ProjectWorkerAssignmentRead],
)
async def list_project_worker_assignments(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectWorkerAssignment]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.assignment.view")
    rows = await db.scalars(
        select(ProjectWorkerAssignment)
        .where(
            ProjectWorkerAssignment.organization_id == context.organization_id,
            ProjectWorkerAssignment.project_id == project_id,
        )
        .order_by(ProjectWorkerAssignment.created_at, ProjectWorkerAssignment.id)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/workforce/assignments",
    response_model=ProjectWorkerAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_worker_route(
    project_id: UUID,
    payload: ProjectWorkerAssignmentCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectWorkerAssignment:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.assignment.manage")
    try:
        assignment = await assign_worker_to_project(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(assignment)
        return assignment
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


async def _timecard_detail(db: DbSession, timecard: Timecard) -> TimecardDetailRead:
    entries = list(
        (
            await db.scalars(
                select(TimeEntry)
                .where(
                    TimeEntry.organization_id == timecard.organization_id,
                    TimeEntry.timecard_id == timecard.id,
                )
                .order_by(TimeEntry.work_date, TimeEntry.created_at, TimeEntry.id)
            )
        ).all()
    )
    return TimecardDetailRead(
        **TimecardRead.model_validate(timecard).model_dump(),
        entries=[TimeEntryRead.model_validate(entry) for entry in entries],
    )


@router.get(
    "/projects/{project_id}/timecards",
    response_model=list[TimecardRead],
)
async def list_timecards(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[Timecard]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.timecard.view")
    rows = await db.scalars(
        select(Timecard)
        .where(
            Timecard.organization_id == context.organization_id,
            Timecard.project_id == project_id,
        )
        .order_by(Timecard.week_start.desc(), Timecard.worker_id)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/timecards",
    response_model=TimecardRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_timecard_route(
    project_id: UUID,
    payload: TimecardCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Timecard:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.timecard.create")
    try:
        timecard = await create_timecard(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            worker_id=payload.worker_id,
            week_start=payload.week_start,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(timecard)
        return timecard
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/projects/{project_id}/timecards/{timecard_id}", response_model=TimecardDetailRead)
async def get_timecard(
    project_id: UUID,
    timecard_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> TimecardDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.timecard.view")
    timecard = await db.scalar(
        select(Timecard).where(
            Timecard.id == timecard_id,
            Timecard.organization_id == context.organization_id,
            Timecard.project_id == project_id,
        )
    )
    if timecard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timecard not found")
    return await _timecard_detail(db, timecard)


@router.put(
    "/projects/{project_id}/timecards/{timecard_id}/entries",
    response_model=TimecardDetailRead,
)
async def replace_timecard_entries_route(
    project_id: UUID,
    timecard_id: UUID,
    payload: TimecardEntriesWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> TimecardDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.timecard.update")
    try:
        timecard = await replace_time_entries(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            timecard_id=timecard_id,
            expected_revision=payload.expected_revision,
            entries=[entry.model_dump() for entry in payload.entries],
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(timecard)
        return await _timecard_detail(db, timecard)
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/projects/{project_id}/timecards/{timecard_id}/submit",
    response_model=TimecardRead,
)
async def submit_timecard_route(
    project_id: UUID,
    timecard_id: UUID,
    payload: TimecardVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Timecard:
    context = await build_access_context(db, session.membership_id)
    permissions = _require_project_permission(context, project_id, "workforce.timecard.submit")
    try:
        timecard = await submit_timecard(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            timecard_id=timecard_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            permission_keys=permissions,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(timecard)
        return timecard
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/projects/{project_id}/timecards/{timecard_id}/approve",
    response_model=TimecardRead,
)
async def approve_timecard_route(
    project_id: UUID,
    timecard_id: UUID,
    payload: TimecardVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Timecard:
    context = await build_access_context(db, session.membership_id)
    permissions = _require_project_permission(context, project_id, "workforce.timecard.approve")
    try:
        timecard = await review_timecard(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            timecard_id=timecard_id,
            expected_revision=payload.expected_revision,
            approve=True,
            actor_user_id=session.user_id,
            permission_keys=permissions,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(timecard)
        return timecard
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/projects/{project_id}/timecards/{timecard_id}/reject",
    response_model=TimecardRead,
)
async def reject_timecard_route(
    project_id: UUID,
    timecard_id: UUID,
    payload: TimecardReject,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Timecard:
    context = await build_access_context(db, session.membership_id)
    permissions = _require_project_permission(context, project_id, "workforce.timecard.approve")
    try:
        timecard = await review_timecard(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            timecard_id=timecard_id,
            expected_revision=payload.expected_revision,
            approve=False,
            actor_user_id=session.user_id,
            permission_keys=permissions,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(timecard)
        return timecard
    except (WorkforceConflictError, WorkforceValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/timecards/{timecard_id}/history",
    response_model=list[TimecardHistoryRead],
)
async def timecard_history(
    project_id: UUID,
    timecard_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[TimecardHistoryEvent]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "workforce.timecard.view")
    exists = await db.scalar(
        select(Timecard.id).where(
            Timecard.id == timecard_id,
            Timecard.organization_id == context.organization_id,
            Timecard.project_id == project_id,
        )
    )
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timecard not found")
    rows = await db.scalars(
        select(TimecardHistoryEvent)
        .where(
            TimecardHistoryEvent.organization_id == context.organization_id,
            TimecardHistoryEvent.timecard_id == timecard_id,
        )
        .order_by(TimecardHistoryEvent.created_at, TimecardHistoryEvent.id)
    )
    return list(rows.all())
