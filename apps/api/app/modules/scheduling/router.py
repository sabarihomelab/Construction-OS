from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.scheduling.models import (
    ProjectSchedule,
    ScheduleActivity,
    ScheduleBaseline,
    ScheduleDependency,
    ScheduleProgressUpdate,
)
from app.modules.scheduling.schemas import (
    ActivityCreate,
    ActivityRead,
    ActivityUpdate,
    BaselineCreate,
    BaselineRead,
    DependencyCreate,
    DependencyRead,
    ProgressCreate,
    ProgressRead,
    ScheduleCreate,
    ScheduleRead,
    ScheduleSummary,
    ScheduleUpdate,
)
from app.modules.scheduling.service import (
    SchedulingConflictError,
    SchedulingValidationError,
    add_activity,
    add_dependency,
    complete_schedule,
    create_baseline,
    create_schedule,
    record_progress,
    schedule_summary,
    update_activity,
    update_schedule,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["scheduling"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, SchedulingConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/projects/{project_id}/scheduling/schedules", response_model=list[ScheduleRead])
async def list_schedules(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectSchedule]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.view")
    rows = await db.scalars(
        select(ProjectSchedule)
        .where(
            ProjectSchedule.organization_id == context.organization_id,
            ProjectSchedule.project_id == project_id,
        )
        .order_by(ProjectSchedule.name)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/scheduling/schedules",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_route(
    project_id: UUID,
    payload: ScheduleCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectSchedule:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.manage")
    try:
        row = await create_schedule(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}",
    response_model=ScheduleRead,
)
async def update_schedule_route(
    project_id: UUID,
    schedule_id: UUID,
    payload: ScheduleUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectSchedule:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.manage")
    try:
        row = await update_schedule(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/activities",
    response_model=list[ActivityRead],
)
async def list_activities(
    project_id: UUID,
    schedule_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ScheduleActivity]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.view")
    rows = await db.scalars(
        select(ScheduleActivity)
        .where(
            ScheduleActivity.organization_id == context.organization_id,
            ScheduleActivity.project_id == project_id,
            ScheduleActivity.schedule_id == schedule_id,
        )
        .order_by(ScheduleActivity.planned_start, ScheduleActivity.activity_code)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/activities",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_activity_route(
    project_id: UUID,
    schedule_id: UUID,
    payload: ActivityCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ScheduleActivity:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.manage")
    try:
        row = await add_activity(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/activities/{activity_id}",
    response_model=ActivityRead,
)
async def update_activity_route(
    project_id: UUID,
    schedule_id: UUID,
    activity_id: UUID,
    payload: ActivityUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ScheduleActivity:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.manage")
    try:
        row = await update_activity(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            activity_id=activity_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/dependencies",
    response_model=list[DependencyRead],
)
async def list_dependencies(
    project_id: UUID,
    schedule_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ScheduleDependency]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.view")
    rows = await db.scalars(
        select(ScheduleDependency).where(
            ScheduleDependency.organization_id == context.organization_id,
            ScheduleDependency.project_id == project_id,
            ScheduleDependency.schedule_id == schedule_id,
        )
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/dependencies",
    response_model=DependencyRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_dependency_route(
    project_id: UUID,
    schedule_id: UUID,
    payload: DependencyCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ScheduleDependency:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.manage")
    try:
        row = await add_dependency(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            predecessor_activity_id=payload.predecessor_activity_id,
            successor_activity_id=payload.successor_activity_id,
            dependency_type=payload.dependency_type,
            lag_days=payload.lag_days,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/baselines",
    response_model=BaselineRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_baseline_route(
    project_id: UUID,
    schedule_id: UUID,
    payload: BaselineCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ScheduleBaseline:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.baseline.create")
    try:
        row = await create_baseline(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            expected_revision=payload.expected_revision,
            created_by_membership_id=session.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/baselines",
    response_model=list[BaselineRead],
)
async def list_baselines(
    project_id: UUID,
    schedule_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ScheduleBaseline]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.view")
    rows = await db.scalars(
        select(ScheduleBaseline)
        .where(
            ScheduleBaseline.organization_id == context.organization_id,
            ScheduleBaseline.project_id == project_id,
            ScheduleBaseline.schedule_id == schedule_id,
        )
        .order_by(ScheduleBaseline.version_number.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/activities/{activity_id}/progress",
    response_model=ProgressRead,
    status_code=status.HTTP_201_CREATED,
)
async def record_progress_route(
    project_id: UUID,
    schedule_id: UUID,
    activity_id: UUID,
    payload: ProgressCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ScheduleProgressUpdate:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.progress.update")
    try:
        row = await record_progress(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            activity_id=activity_id,
            expected_activity_revision=payload.expected_activity_revision,
            data_date=payload.data_date,
            percent_complete=payload.percent_complete,
            actual_start=payload.actual_start,
            actual_finish=payload.actual_finish,
            recorded_by_membership_id=session.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            remarks=payload.remarks,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/activities/{activity_id}/progress",
    response_model=list[ProgressRead],
)
async def list_progress(
    project_id: UUID,
    schedule_id: UUID,
    activity_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ScheduleProgressUpdate]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.view")
    rows = await db.scalars(
        select(ScheduleProgressUpdate)
        .where(
            ScheduleProgressUpdate.organization_id == context.organization_id,
            ScheduleProgressUpdate.project_id == project_id,
            ScheduleProgressUpdate.schedule_id == schedule_id,
            ScheduleProgressUpdate.activity_id == activity_id,
        )
        .order_by(ScheduleProgressUpdate.data_date.desc(), ScheduleProgressUpdate.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/complete",
    response_model=ScheduleRead,
)
async def complete_schedule_route(
    project_id: UUID,
    schedule_id: UUID,
    payload: BaselineCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectSchedule:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.complete")
    try:
        row = await complete_schedule(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (SchedulingConflictError, SchedulingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/scheduling/schedules/{schedule_id}/summary",
    response_model=ScheduleSummary,
)
async def get_schedule_summary(
    project_id: UUID,
    schedule_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> ScheduleSummary:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "scheduling.schedule.view")
    try:
        schedule, count, completed, average = await schedule_summary(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            schedule_id=schedule_id,
        )
        return ScheduleSummary(
            schedule=ScheduleRead.model_validate(schedule),
            activity_count=count,
            completed_activity_count=completed,
            average_percent_complete=average,
            baseline_version=schedule.active_baseline_version,
        )
    except SchedulingValidationError as exc:
        _domain_error(exc)
