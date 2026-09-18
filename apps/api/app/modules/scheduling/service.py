from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import WBSCode
from app.modules.events.service import enqueue_event
from app.modules.identity.models import MembershipStatus, OrganizationMembership
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.scheduling.models import (
    ActivityStatus,
    DependencyType,
    ProjectSchedule,
    ScheduleActivity,
    ScheduleBaseline,
    ScheduleDependency,
    ScheduleProgressUpdate,
    ScheduleStatus,
)
from app.modules.search.service import schedule_search_index


class SchedulingValidationError(ValueError):
    pass


class SchedulingConflictError(ValueError):
    pass


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> Project:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise SchedulingValidationError("Project was not found")
    return project


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    member = await db.scalar(
        select(ProjectMembership.id)
        .join(
            OrganizationMembership,
            (OrganizationMembership.id == ProjectMembership.organization_membership_id)
            & (OrganizationMembership.organization_id == ProjectMembership.organization_id),
        )
        .where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if member is None:
        raise SchedulingValidationError("Selected person must be an active member of this project")


async def _publish(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    entity_version: int,
    permission: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key=permission,
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": entity_version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
    )


async def create_schedule(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectSchedule:
    await _require_project(db, organization_id, project_id)
    data = dict(values)
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise SchedulingValidationError("Schedule code and name are required")
    duplicate = await db.scalar(
        select(ProjectSchedule.id).where(
            ProjectSchedule.project_id == project_id,
            ProjectSchedule.code == code,
        )
    )
    if duplicate is not None:
        raise SchedulingConflictError("Schedule code already exists in this project")
    data["code"] = code
    data["name"] = name
    row = ProjectSchedule(organization_id=organization_id, project_id=project_id, **data)
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.schedule.created",
        target_type="project_schedule",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"project_id": str(project_id), "code": row.code, "name": row.name},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.schedule.created",
        entity_type="project_schedule",
        entity_id=row.id,
        entity_version=row.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def update_schedule(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectSchedule:
    row = await db.scalar(
        select(ProjectSchedule)
        .where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
        .with_for_update()
    )
    if row is None:
        raise SchedulingValidationError("Schedule was not found")
    if row.revision != expected_revision:
        raise SchedulingConflictError("Schedule changed; refresh before saving")
    if row.status in {ScheduleStatus.COMPLETED, ScheduleStatus.ARCHIVED}:
        raise SchedulingValidationError("Completed or archived schedules cannot be edited")
    before = {"name": row.name, "data_date": str(row.data_date), "revision": row.revision}
    for key in ("name", "description", "data_date", "notes"):
        if key in changes:
            value = changes[key]
            if key == "name" and isinstance(value, str):
                value = value.strip()
                if not value:
                    raise SchedulingValidationError("Schedule name cannot be blank")
            setattr(row, key, value)
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.schedule.updated",
        target_type="project_schedule",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "before": before,
            "after": {"name": row.name, "data_date": str(row.data_date), "revision": row.revision},
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.schedule.updated",
        entity_type="project_schedule",
        entity_id=row.id,
        entity_version=row.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def add_activity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ScheduleActivity:
    schedule = await db.scalar(
        select(ProjectSchedule)
        .where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
        .with_for_update()
    )
    if schedule is None:
        raise SchedulingValidationError("Schedule was not found")
    if schedule.status in {ScheduleStatus.COMPLETED, ScheduleStatus.ARCHIVED}:
        raise SchedulingValidationError("Completed or archived schedules cannot be edited")
    data = dict(values)
    code = str(data.get("activity_code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise SchedulingValidationError("Activity code and name are required")
    planned_start = data.get("planned_start")
    planned_finish = data.get("planned_finish")
    if not isinstance(planned_start, date) or not isinstance(planned_finish, date):
        raise SchedulingValidationError("Planned start and finish are required")
    if planned_finish < planned_start:
        raise SchedulingValidationError("Planned finish cannot be before planned start")
    duplicate = await db.scalar(
        select(ScheduleActivity.id).where(
            ScheduleActivity.schedule_id == schedule_id,
            ScheduleActivity.activity_code == code,
        )
    )
    if duplicate is not None:
        raise SchedulingConflictError("Activity code already exists in this schedule")
    wbs_id = data.get("wbs_code_id")
    if isinstance(wbs_id, UUID):
        exists_wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if exists_wbs is None:
            raise SchedulingValidationError("WBS code was not found in this project")
    member_id = data.get("responsible_membership_id")
    if isinstance(member_id, UUID):
        await _require_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=member_id,
        )
    data["activity_code"] = code
    data["name"] = name
    row = ScheduleActivity(
        organization_id=organization_id,
        project_id=project_id,
        schedule_id=schedule_id,
        **data,
    )
    db.add(row)
    schedule.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.activity.created",
        target_type="schedule_activity",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"schedule_id": str(schedule_id), "activity_code": row.activity_code},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.activity.created",
        entity_type="schedule_activity",
        entity_id=row.id,
        entity_version=row.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def update_activity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    activity_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ScheduleActivity:
    row = await db.scalar(
        select(ScheduleActivity)
        .where(
            ScheduleActivity.id == activity_id,
            ScheduleActivity.schedule_id == schedule_id,
            ScheduleActivity.organization_id == organization_id,
            ScheduleActivity.project_id == project_id,
        )
        .with_for_update()
    )
    if row is None:
        raise SchedulingValidationError("Activity was not found")
    if row.revision != expected_revision:
        raise SchedulingConflictError("Activity changed; refresh before saving")
    schedule = await db.scalar(
        select(ProjectSchedule).where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
    )
    if schedule is None or schedule.status in {ScheduleStatus.COMPLETED, ScheduleStatus.ARCHIVED}:
        raise SchedulingValidationError("Schedule cannot be edited")
    if "wbs_code_id" in changes and isinstance(changes.get("wbs_code_id"), UUID):
        wbs_id = changes["wbs_code_id"]
        valid_wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if valid_wbs is None:
            raise SchedulingValidationError("WBS code was not found in this project")
    if "responsible_membership_id" in changes and isinstance(
        changes.get("responsible_membership_id"), UUID
    ):
        await _require_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=changes["responsible_membership_id"],
        )
    planned_start = changes.get("planned_start", row.planned_start)
    planned_finish = changes.get("planned_finish", row.planned_finish)
    if isinstance(planned_start, date) and isinstance(planned_finish, date):
        if planned_finish < planned_start:
            raise SchedulingValidationError("Planned finish cannot be before planned start")
    for key in (
        "name",
        "description",
        "wbs_code_id",
        "responsible_membership_id",
        "planned_start",
        "planned_finish",
        "status",
        "notes",
    ):
        if key in changes:
            setattr(row, key, changes[key])
    row.revision += 1
    schedule.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.activity.updated",
        target_type="schedule_activity",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"activity_code": row.activity_code, "revision": row.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.activity.updated",
        entity_type="schedule_activity",
        entity_id=row.id,
        entity_version=row.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def _would_create_cycle(
    db: AsyncSession,
    *,
    schedule_id: UUID,
    predecessor_id: UUID,
    successor_id: UUID,
) -> bool:
    rows = await db.execute(
        select(
            ScheduleDependency.predecessor_activity_id,
            ScheduleDependency.successor_activity_id,
        ).where(ScheduleDependency.schedule_id == schedule_id)
    )
    adjacency: dict[UUID, set[UUID]] = defaultdict(set)
    for predecessor, successor in rows.all():
        adjacency[predecessor].add(successor)
    adjacency[predecessor_id].add(successor_id)
    pending = [successor_id]
    seen: set[UUID] = set()
    while pending:
        node = pending.pop()
        if node == predecessor_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        pending.extend(adjacency.get(node, ()))
    return False


async def add_dependency(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    predecessor_activity_id: UUID,
    successor_activity_id: UUID,
    dependency_type: DependencyType,
    lag_days: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ScheduleDependency:
    if predecessor_activity_id == successor_activity_id:
        raise SchedulingValidationError("An activity cannot depend on itself")
    activities = await db.scalars(
        select(ScheduleActivity).where(
            ScheduleActivity.id.in_([predecessor_activity_id, successor_activity_id]),
            ScheduleActivity.schedule_id == schedule_id,
            ScheduleActivity.organization_id == organization_id,
            ScheduleActivity.project_id == project_id,
        )
    )
    if len(list(activities.all())) != 2:
        raise SchedulingValidationError("Both activities must belong to this schedule")
    if await _would_create_cycle(
        db,
        schedule_id=schedule_id,
        predecessor_id=predecessor_activity_id,
        successor_id=successor_activity_id,
    ):
        raise SchedulingValidationError("Dependency would create a schedule cycle")
    duplicate = await db.scalar(
        select(ScheduleDependency.id).where(
            ScheduleDependency.predecessor_activity_id == predecessor_activity_id,
            ScheduleDependency.successor_activity_id == successor_activity_id,
            ScheduleDependency.dependency_type == dependency_type,
        )
    )
    if duplicate is not None:
        raise SchedulingConflictError("Dependency already exists")
    row = ScheduleDependency(
        organization_id=organization_id,
        project_id=project_id,
        schedule_id=schedule_id,
        predecessor_activity_id=predecessor_activity_id,
        successor_activity_id=successor_activity_id,
        dependency_type=dependency_type,
        lag_days=lag_days,
    )
    db.add(row)
    schedule = await db.scalar(
        select(ProjectSchedule)
        .where(ProjectSchedule.id == schedule_id, ProjectSchedule.organization_id == organization_id)
        .with_for_update()
    )
    if schedule is None:
        raise SchedulingValidationError("Schedule was not found")
    schedule.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.dependency.created",
        target_type="schedule_dependency",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={
            "predecessor_activity_id": str(predecessor_activity_id),
            "successor_activity_id": str(successor_activity_id),
            "dependency_type": dependency_type.value,
            "lag_days": lag_days,
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.dependency.created",
        entity_type="project_schedule",
        entity_id=schedule.id,
        entity_version=schedule.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def create_baseline(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    expected_revision: int,
    created_by_membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ScheduleBaseline:
    schedule = await db.scalar(
        select(ProjectSchedule)
        .where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
        .with_for_update()
    )
    if schedule is None:
        raise SchedulingValidationError("Schedule was not found")
    if schedule.revision != expected_revision:
        raise SchedulingConflictError("Schedule changed; refresh before baselining")
    if schedule.status in {ScheduleStatus.COMPLETED, ScheduleStatus.ARCHIVED}:
        raise SchedulingValidationError("Completed or archived schedules cannot be baselined")
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=created_by_membership_id,
    )
    activities = list(
        (
            await db.scalars(
                select(ScheduleActivity)
                .where(ScheduleActivity.schedule_id == schedule_id)
                .order_by(ScheduleActivity.activity_code)
            )
        ).all()
    )
    if not activities:
        raise SchedulingValidationError("At least one activity is required before baselining")
    dependencies = list(
        (
            await db.scalars(
                select(ScheduleDependency).where(ScheduleDependency.schedule_id == schedule_id)
            )
        ).all()
    )
    version_number = (
        await db.scalar(
            select(func.coalesce(func.max(ScheduleBaseline.version_number), 0)).where(
                ScheduleBaseline.schedule_id == schedule_id
            )
        )
    ) + 1
    snapshot = {
        "activities": [
            {
                "id": str(item.id),
                "activity_code": item.activity_code,
                "name": item.name,
                "wbs_code_id": str(item.wbs_code_id) if item.wbs_code_id else None,
                "planned_start": item.planned_start.isoformat(),
                "planned_finish": item.planned_finish.isoformat(),
            }
            for item in activities
        ],
        "dependencies": [
            {
                "predecessor_activity_id": str(item.predecessor_activity_id),
                "successor_activity_id": str(item.successor_activity_id),
                "dependency_type": item.dependency_type.value,
                "lag_days": item.lag_days,
            }
            for item in dependencies
        ],
    }
    baseline = ScheduleBaseline(
        organization_id=organization_id,
        project_id=project_id,
        schedule_id=schedule_id,
        version_number=version_number,
        created_by_membership_id=created_by_membership_id,
        reason=reason,
        snapshot=snapshot,
    )
    db.add(baseline)
    schedule.active_baseline_version = version_number
    schedule.status = ScheduleStatus.ACTIVE
    schedule.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.baseline.created",
        target_type="schedule_baseline",
        target_id=str(baseline.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"schedule_id": str(schedule_id), "version_number": version_number},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.baseline.created",
        entity_type="project_schedule",
        entity_id=schedule.id,
        entity_version=schedule.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return baseline


async def record_progress(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    activity_id: UUID,
    expected_activity_revision: int,
    data_date: date,
    percent_complete: Decimal,
    actual_start: date | None,
    actual_finish: date | None,
    recorded_by_membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    remarks: str | None = None,
) -> ScheduleProgressUpdate:
    schedule = await db.scalar(
        select(ProjectSchedule).where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
    )
    if schedule is None or schedule.status != ScheduleStatus.ACTIVE:
        raise SchedulingValidationError("Schedule must be baselined and active before progress is recorded")
    activity = await db.scalar(
        select(ScheduleActivity)
        .where(
            ScheduleActivity.id == activity_id,
            ScheduleActivity.schedule_id == schedule_id,
            ScheduleActivity.organization_id == organization_id,
            ScheduleActivity.project_id == project_id,
        )
        .with_for_update()
    )
    if activity is None:
        raise SchedulingValidationError("Activity was not found")
    if activity.revision != expected_activity_revision:
        raise SchedulingConflictError("Activity changed; refresh before recording progress")
    percent_complete = Decimal(percent_complete)
    if percent_complete < activity.percent_complete:
        raise SchedulingValidationError("Progress cannot decrease; use a controlled correction workflow")
    if percent_complete == 100 and actual_finish is None:
        raise SchedulingValidationError("Actual finish is required at 100% completion")
    if actual_start and actual_finish and actual_finish < actual_start:
        raise SchedulingValidationError("Actual finish cannot be before actual start")
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=recorded_by_membership_id,
    )
    update = ScheduleProgressUpdate(
        organization_id=organization_id,
        project_id=project_id,
        schedule_id=schedule_id,
        activity_id=activity_id,
        data_date=data_date,
        percent_complete=percent_complete,
        actual_start=actual_start,
        actual_finish=actual_finish,
        recorded_by_membership_id=recorded_by_membership_id,
        recorded_at=datetime.now(UTC),
        remarks=remarks,
    )
    db.add(update)
    activity.percent_complete = percent_complete
    if actual_start is not None:
        activity.actual_start = actual_start
    if actual_finish is not None:
        activity.actual_finish = actual_finish
    if percent_complete == 100:
        activity.status = ActivityStatus.COMPLETED
    elif percent_complete > 0:
        activity.status = ActivityStatus.IN_PROGRESS
    elif activity.status == ActivityStatus.COMPLETED:
        activity.status = ActivityStatus.NOT_STARTED
    activity.revision += 1
    schedule.data_date = data_date
    schedule.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.progress.recorded",
        target_type="schedule_progress_update",
        target_id=str(update.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "activity_id": str(activity_id),
            "percent_complete": str(percent_complete),
            "data_date": data_date.isoformat(),
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.progress.recorded",
        entity_type="schedule_activity",
        entity_id=activity.id,
        entity_version=activity.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return update


async def complete_schedule(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectSchedule:
    schedule = await db.scalar(
        select(ProjectSchedule)
        .where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
        .with_for_update()
    )
    if schedule is None:
        raise SchedulingValidationError("Schedule was not found")
    if schedule.revision != expected_revision:
        raise SchedulingConflictError("Schedule changed; refresh before completing")
    if schedule.status != ScheduleStatus.ACTIVE:
        raise SchedulingValidationError("Only an active schedule can be completed")
    incomplete = await db.scalar(
        select(func.count())
        .select_from(ScheduleActivity)
        .where(
            ScheduleActivity.schedule_id == schedule_id,
            ScheduleActivity.status != ActivityStatus.COMPLETED,
        )
    )
    if incomplete:
        raise SchedulingValidationError("All schedule activities must be complete")
    schedule.status = ScheduleStatus.COMPLETED
    schedule.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="scheduling.schedule.completed",
        target_type="project_schedule",
        target_id=str(schedule.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": schedule.status.value, "revision": schedule.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="scheduling.schedule.completed",
        entity_type="project_schedule",
        entity_id=schedule.id,
        entity_version=schedule.revision,
        permission="scheduling.schedule.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return schedule


async def schedule_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    schedule_id: UUID,
) -> tuple[ProjectSchedule, int, int, Decimal]:
    schedule = await db.scalar(
        select(ProjectSchedule).where(
            ProjectSchedule.id == schedule_id,
            ProjectSchedule.organization_id == organization_id,
            ProjectSchedule.project_id == project_id,
        )
    )
    if schedule is None:
        raise SchedulingValidationError("Schedule was not found")
    activities = list(
        (
            await db.scalars(
                select(ScheduleActivity).where(ScheduleActivity.schedule_id == schedule_id)
            )
        ).all()
    )
    activity_count = len(activities)
    completed = sum(1 for item in activities if item.status == ActivityStatus.COMPLETED)
    average = (
        sum((Decimal(item.percent_complete) for item in activities), Decimal(0)) / activity_count
        if activity_count
        else Decimal(0)
    )
    return schedule, activity_count, completed, average
