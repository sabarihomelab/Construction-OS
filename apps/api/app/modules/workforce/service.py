from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.configuration.schemas import EffectiveConfigurationRead
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.events.service import enqueue_event
from app.modules.identity.models import OrganizationMembership
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index
from app.modules.workflows.models import WorkflowInstance, WorkflowInstanceStatus
from app.modules.workflows.service import (
    WorkflowValidationError,
    execute_transition,
    start_workflow_instance,
)
from app.modules.workforce.models import (
    Crew,
    CrewMembership,
    CrewStatus,
    EmploymentStatus,
    ProjectWorkerAssignment,
    ProjectWorkerAssignmentStatus,
    Timecard,
    TimecardHistoryEvent,
    TimecardHistoryType,
    TimecardStatus,
    TimeEntry,
    Worker,
)


class WorkforceValidationError(ValueError):
    pass


class WorkforceConflictError(WorkforceValidationError):
    pass


WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _setting(config: EffectiveConfigurationRead, key: str, default: object) -> object:
    for setting in config.settings:
        if setting.key == key:
            return setting.value
    return default


def _clean_text(value: object, *, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise WorkforceValidationError(f"{field} is required")
        return None
    normalized = str(value).strip()
    if required and not normalized:
        raise WorkforceValidationError(f"{field} is required")
    return normalized or None


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    project = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise WorkforceValidationError("Project was not found")


async def _require_worker(db: AsyncSession, organization_id: UUID, worker_id: UUID) -> Worker:
    worker = await db.scalar(
        select(Worker).where(
            Worker.id == worker_id,
            Worker.organization_id == organization_id,
        )
    )
    if worker is None:
        raise WorkforceValidationError("Worker was not found")
    return worker


async def _require_crew(db: AsyncSession, organization_id: UUID, crew_id: UUID) -> Crew:
    crew = await db.scalar(
        select(Crew).where(Crew.id == crew_id, Crew.organization_id == organization_id)
    )
    if crew is None:
        raise WorkforceValidationError("Crew was not found")
    return crew


async def _publish_worker_change(
    db: AsyncSession,
    *,
    worker: Worker,
    event_type: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=worker.organization_id,
        event_type=event_type,
        entity_type="worker",
        entity_id=worker.id,
        entity_version=worker.revision,
        required_permission_key="workforce.worker.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": worker.revision, "status": worker.status.value},
    )
    await schedule_search_index(
        db,
        organization_id=worker.organization_id,
        entity_type="worker",
        entity_id=worker.id,
        entity_version=worker.revision,
    )


async def create_worker(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> Worker:
    data = dict(values)
    data["worker_number"] = _clean_text(
        data.get("worker_number"), field="Worker number", required=True
    )
    data["first_name"] = _clean_text(data.get("first_name"), field="First name", required=True)
    data["last_name"] = _clean_text(data.get("last_name"), field="Last name", required=True)

    membership_id = data.get("organization_membership_id")
    if membership_id is not None:
        membership = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.id == membership_id,
                OrganizationMembership.organization_id == organization_id,
            )
        )
        if membership is None:
            raise WorkforceValidationError("Linked application membership was not found")

    duplicate = await db.scalar(
        select(Worker.id).where(
            Worker.organization_id == organization_id,
            Worker.worker_number == data["worker_number"],
        )
    )
    if duplicate is not None:
        raise WorkforceConflictError("Worker number already exists")

    worker = Worker(organization_id=organization_id, **data)
    db.add(worker)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.worker.created",
        target_type="worker",
        target_id=str(worker.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"worker_number": worker.worker_number, "status": worker.status.value},
    )
    await _publish_worker_change(
        db,
        worker=worker,
        event_type="workforce.worker.created",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return worker


async def update_worker(
    db: AsyncSession,
    *,
    organization_id: UUID,
    worker_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Worker:
    worker = await db.scalar(
        select(Worker)
        .where(Worker.id == worker_id, Worker.organization_id == organization_id)
        .with_for_update()
    )
    if worker is None:
        raise WorkforceValidationError("Worker was not found")
    if worker.revision != expected_revision:
        raise WorkforceConflictError(
            f"Worker changed from revision {expected_revision} to {worker.revision}; refresh before saving"
        )

    before = {"worker_number": worker.worker_number, "status": worker.status.value}
    mutable = {
        "worker_number",
        "first_name",
        "last_name",
        "preferred_name",
        "email",
        "phone",
        "job_title",
        "trade",
        "classification",
        "hire_date",
        "termination_date",
        "status",
        "organization_membership_id",
    }
    for key, value in changes.items():
        if key not in mutable:
            continue
        if key in {"worker_number", "first_name", "last_name"}:
            value = _clean_text(value, field=key.replace("_", " ").title(), required=True)
        elif key in {"preferred_name", "email", "phone", "job_title", "trade", "classification"}:
            value = _clean_text(value, field=key)
        setattr(worker, key, value)

    if worker.organization_membership_id is not None:
        linked = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.id == worker.organization_membership_id,
                OrganizationMembership.organization_id == organization_id,
            )
        )
        if linked is None:
            raise WorkforceValidationError("Linked application membership was not found")
    if worker.hire_date and worker.termination_date and worker.termination_date < worker.hire_date:
        raise WorkforceValidationError("Termination date cannot be before hire date")

    duplicate = await db.scalar(
        select(Worker.id).where(
            Worker.organization_id == organization_id,
            Worker.worker_number == worker.worker_number,
            Worker.id != worker.id,
        )
    )
    if duplicate is not None:
        raise WorkforceConflictError("Worker number already exists")

    worker.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.worker.updated",
        target_type="worker",
        target_id=str(worker.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": before, "after": {"worker_number": worker.worker_number, "status": worker.status.value}},
    )
    await _publish_worker_change(
        db,
        worker=worker,
        event_type="workforce.worker.updated",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return worker


async def create_crew(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> Crew:
    data = dict(values)
    data["name"] = _clean_text(data.get("name"), field="Crew name", required=True)
    supervisor_id = data.get("supervisor_worker_id")
    if supervisor_id is not None:
        await _require_worker(db, organization_id, UUID(str(supervisor_id)))
    duplicate = await db.scalar(
        select(Crew.id).where(Crew.organization_id == organization_id, Crew.name == data["name"])
    )
    if duplicate is not None:
        raise WorkforceConflictError("Crew name already exists")

    crew = Crew(organization_id=organization_id, **data)
    db.add(crew)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.crew.created",
        target_type="crew",
        target_id=str(crew.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"name": crew.name},
    )
    return crew


async def add_crew_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    crew_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> CrewMembership:
    crew = await _require_crew(db, organization_id, crew_id)
    worker_id = UUID(str(values["worker_id"]))
    worker = await _require_worker(db, organization_id, worker_id)
    if crew.status != CrewStatus.ACTIVE or worker.status != EmploymentStatus.ACTIVE:
        raise WorkforceValidationError("Only active crews and workers can receive new memberships")
    membership = CrewMembership(organization_id=organization_id, crew_id=crew_id, **dict(values))
    db.add(membership)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.crew.membership.created",
        target_type="crew",
        target_id=str(crew.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"worker_id": str(worker_id), "effective_from": membership.effective_from},
    )
    return membership


async def assign_worker_to_project(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> ProjectWorkerAssignment:
    await _require_project(db, organization_id, project_id)
    data = dict(values)
    worker = await _require_worker(db, organization_id, UUID(str(data["worker_id"])))
    if worker.status != EmploymentStatus.ACTIVE:
        raise WorkforceValidationError("Only an active worker can be assigned to a project")
    crew_id = data.get("crew_id")
    if crew_id is not None:
        crew = await _require_crew(db, organization_id, UUID(str(crew_id)))
        if crew.status != CrewStatus.ACTIVE:
            raise WorkforceValidationError("Only an active crew can be assigned")

    existing = await db.scalar(
        select(ProjectWorkerAssignment).where(
            ProjectWorkerAssignment.organization_id == organization_id,
            ProjectWorkerAssignment.project_id == project_id,
            ProjectWorkerAssignment.worker_id == worker.id,
        )
    )
    if existing is not None:
        if existing.status == ProjectWorkerAssignmentStatus.ACTIVE:
            return existing
        existing.status = ProjectWorkerAssignmentStatus.ACTIVE
        existing.crew_id = data.get("crew_id")
        existing.project_role = data.get("project_role")
        existing.trade = data.get("trade")
        existing.default_cost_code = data.get("default_cost_code")
        existing.start_date = data.get("start_date")
        existing.end_date = data.get("end_date")
        existing.revision += 1
        assignment = existing
    else:
        assignment = ProjectWorkerAssignment(
            organization_id=organization_id,
            project_id=project_id,
            **data,
        )
        db.add(assignment)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.project_assignment.changed",
        target_type="project_worker_assignment",
        target_id=str(assignment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "worker_id": str(worker.id), "status": assignment.status.value},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workforce.project_assignment.changed",
        entity_type="project_worker_assignment",
        entity_id=assignment.id,
        entity_version=assignment.revision,
        required_permission_key="workforce.assignment.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"worker_id": str(worker.id), "status": assignment.status.value},
    )
    return assignment


async def _load_timecard_for_update(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    timecard_id: UUID,
    expected_revision: int,
) -> Timecard:
    timecard = await db.scalar(
        select(Timecard)
        .where(
            Timecard.id == timecard_id,
            Timecard.organization_id == organization_id,
            Timecard.project_id == project_id,
        )
        .with_for_update()
    )
    if timecard is None:
        raise WorkforceValidationError("Timecard was not found")
    if timecard.revision != expected_revision:
        raise WorkforceConflictError(
            f"Timecard changed from revision {expected_revision} to {timecard.revision}; refresh before saving"
        )
    return timecard


async def _timecard_history(
    db: AsyncSession,
    *,
    timecard: Timecard,
    event_type: TimecardHistoryType,
    actor_user_id: UUID,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        TimecardHistoryEvent(
            organization_id=timecard.organization_id,
            timecard_id=timecard.id,
            event_type=event_type,
            timecard_revision=timecard.revision,
            actor_user_id=actor_user_id,
            details=details or {},
        )
    )


async def _publish_timecard_change(
    db: AsyncSession,
    *,
    timecard: Timecard,
    event_type: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=timecard.organization_id,
        event_type=event_type,
        entity_type="timecard",
        entity_id=timecard.id,
        entity_version=timecard.revision,
        required_permission_key="workforce.timecard.view",
        scope_type="project",
        scope_id=timecard.project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"worker_id": str(timecard.worker_id), "status": timecard.status.value, "revision": timecard.revision},
    )
    await schedule_search_index(
        db,
        organization_id=timecard.organization_id,
        entity_type="timecard",
        entity_id=timecard.id,
        entity_version=timecard.revision,
    )


async def _effective_time_config(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    project_id: UUID,
) -> EffectiveConfigurationRead:
    return await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="workforce",
        project_id=project_id,
    )


async def create_timecard(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    worker_id: UUID,
    week_start: date,
    session_id: UUID | None = None,
) -> Timecard:
    await _require_project(db, organization_id, project_id)
    worker = await _require_worker(db, organization_id, worker_id)
    if worker.status != EmploymentStatus.ACTIVE:
        raise WorkforceValidationError("Only an active worker can receive a new timecard")
    assignment = await db.scalar(
        select(ProjectWorkerAssignment.id).where(
            ProjectWorkerAssignment.organization_id == organization_id,
            ProjectWorkerAssignment.project_id == project_id,
            ProjectWorkerAssignment.worker_id == worker_id,
            ProjectWorkerAssignment.status == ProjectWorkerAssignmentStatus.ACTIVE,
        )
    )
    if assignment is None:
        raise WorkforceValidationError("Worker must have an active project assignment")

    config = await _effective_time_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    configured_week_start = str(
        _setting(config, "workforce.timecards.week_start_day", "monday")
    ).lower()
    expected_weekday = WEEKDAY_INDEX.get(configured_week_start)
    if expected_weekday is None:
        raise WorkforceValidationError("Configured timecard week-start day is invalid")
    if week_start.weekday() != expected_weekday:
        raise WorkforceValidationError(
            f"Timecard week must start on configured {configured_week_start.title()}"
        )

    duplicate = await db.scalar(
        select(Timecard.id).where(
            Timecard.organization_id == organization_id,
            Timecard.project_id == project_id,
            Timecard.worker_id == worker_id,
            Timecard.week_start == week_start,
        )
    )
    if duplicate is not None:
        raise WorkforceConflictError("A timecard already exists for this worker, project and week")

    timecard = Timecard(
        organization_id=organization_id,
        project_id=project_id,
        worker_id=worker_id,
        week_start=week_start,
        created_by_user_id=actor_user_id,
    )
    db.add(timecard)
    await db.flush()
    await _timecard_history(
        db,
        timecard=timecard,
        event_type=TimecardHistoryType.CREATED,
        actor_user_id=actor_user_id,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.timecard.created",
        target_type="timecard",
        target_id=str(timecard.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "worker_id": str(worker_id), "week_start": week_start},
    )
    await _publish_timecard_change(
        db,
        timecard=timecard,
        event_type="workforce.timecard.created",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return timecard


async def replace_time_entries(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    timecard_id: UUID,
    expected_revision: int,
    entries: list[Mapping[str, object]],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Timecard:
    timecard = await _load_timecard_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        timecard_id=timecard_id,
        expected_revision=expected_revision,
    )
    if timecard.status not in {TimecardStatus.DRAFT, TimecardStatus.REJECTED}:
        raise WorkforceValidationError("Only draft or rejected timecards can be edited")

    config = await _effective_time_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    require_cost_code = bool(_setting(config, "workforce.timecards.require_cost_code", False))
    overtime_enabled = bool(_setting(config, "workforce.timecards.overtime.enabled", True))
    double_time_enabled = bool(_setting(config, "workforce.timecards.double_time.enabled", False))
    max_daily_hours = Decimal(str(_setting(config, "workforce.timecards.max_daily_hours", "24")))
    week_end = timecard.week_start + timedelta(days=6)

    normalized_entries: list[dict[str, object]] = []
    for raw in entries:
        item = dict(raw)
        work_date = item.get("work_date")
        if not isinstance(work_date, date) or not (timecard.week_start <= work_date <= week_end):
            raise WorkforceValidationError("Every time entry must fall within the timecard week")
        regular = Decimal(str(item.get("regular_hours", 0)))
        overtime = Decimal(str(item.get("overtime_hours", 0)))
        double_time = Decimal(str(item.get("double_time_hours", 0)))
        if any(value < 0 for value in (regular, overtime, double_time)):
            raise WorkforceValidationError("Time entry hours cannot be negative")
        if not overtime_enabled and overtime:
            raise WorkforceValidationError("Overtime is disabled by project configuration")
        if not double_time_enabled and double_time:
            raise WorkforceValidationError("Double time is disabled by project configuration")
        if regular + overtime + double_time > max_daily_hours:
            raise WorkforceValidationError(
                f"Time entry exceeds configured maximum daily hours ({max_daily_hours})"
            )
        cost_code = _clean_text(item.get("cost_code"), field="Cost code")
        if require_cost_code and not cost_code:
            raise WorkforceValidationError("Cost code is required by project configuration")
        item["cost_code"] = cost_code
        normalized_entries.append(item)

    await db.execute(
        delete(TimeEntry).where(
            TimeEntry.organization_id == organization_id,
            TimeEntry.timecard_id == timecard.id,
        )
    )
    for item in normalized_entries:
        db.add(TimeEntry(organization_id=organization_id, timecard_id=timecard.id, **item))

    timecard.revision += 1
    if timecard.status == TimecardStatus.REJECTED:
        timecard.status = TimecardStatus.DRAFT
        timecard.rejected_at = None
    await db.flush()
    await _timecard_history(
        db,
        timecard=timecard,
        event_type=TimecardHistoryType.UPDATED,
        actor_user_id=actor_user_id,
        details={"entry_count": len(normalized_entries), "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.timecard.entries.updated",
        target_type="timecard",
        target_id=str(timecard.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"entry_count": len(normalized_entries), "revision": timecard.revision},
    )
    await _publish_timecard_change(
        db,
        timecard=timecard,
        event_type="workforce.timecard.updated",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return timecard


async def submit_timecard(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    timecard_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    permission_keys: set[str],
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Timecard:
    timecard = await _load_timecard_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        timecard_id=timecard_id,
        expected_revision=expected_revision,
    )
    if timecard.status not in {TimecardStatus.DRAFT, TimecardStatus.REJECTED}:
        raise WorkforceValidationError("Only draft or rejected timecards can be submitted")

    entries = list(
        (
            await db.scalars(
                select(TimeEntry).where(
                    TimeEntry.organization_id == organization_id,
                    TimeEntry.timecard_id == timecard.id,
                )
            )
        ).all()
    )
    if not entries:
        raise WorkforceValidationError("Add at least one time entry before submitting")

    config = await _effective_time_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    approval_required = bool(_setting(config, "workforce.timecards.approval.required", False))
    now = datetime.now(UTC)
    timecard.submitted_at = now
    timecard.configuration_context = {
        "configuration_revisions": config.configuration_revisions,
        "project_template_version_id": (
            str(config.project_template_version_id) if config.project_template_version_id else None
        ),
        "approval_required": approval_required,
        "require_cost_code": bool(
            _setting(config, "workforce.timecards.require_cost_code", False)
        ),
        "week_start_day": _setting(config, "workforce.timecards.week_start_day", "monday"),
        "effective_at": now.isoformat(),
    }

    if approval_required:
        workflow_key = str(
            _setting(config, "workforce.timecards.workflow.definition_key", "")
        ).strip()
        if not workflow_key:
            raise WorkforceValidationError(
                "Timecard approval is enabled but no shared workflow definition is configured"
            )
        if timecard.workflow_instance_id is None:
            try:
                workflow = await start_workflow_instance(
                    db,
                    organization_id=organization_id,
                    definition_key=workflow_key,
                    entity_type="timecard",
                    entity_id=timecard.id,
                    actor_user_id=actor_user_id,
                )
            except WorkflowValidationError as exc:
                raise WorkforceValidationError(str(exc)) from exc
            timecard.workflow_instance_id = workflow.id
        elif timecard.status == TimecardStatus.REJECTED:
            resubmit_key = str(
                _setting(config, "workforce.timecards.workflow.resubmit_transition_key", "")
            ).strip()
            if not resubmit_key:
                raise WorkforceValidationError("Rejected timecard has no configured resubmit transition")
            workflow = await db.get(WorkflowInstance, timecard.workflow_instance_id)
            if workflow is None:
                raise WorkforceValidationError("Timecard workflow instance was not found")
            try:
                await execute_transition(
                    db,
                    workflow_instance_id=workflow.id,
                    organization_id=organization_id,
                    transition_key=resubmit_key,
                    expected_instance_version=workflow.version,
                    permission_keys=permission_keys,
                    actor_user_id=actor_user_id,
                    reason=reason,
                    session_id=session_id,
                    conditions_satisfied=True,
                    approval_completed=True,
                )
            except WorkflowValidationError as exc:
                raise WorkforceValidationError(str(exc)) from exc
        timecard.status = TimecardStatus.IN_REVIEW
    else:
        timecard.status = TimecardStatus.APPROVED
        timecard.approved_at = now

    timecard.rejected_at = None
    timecard.revision += 1
    await db.flush()
    await _timecard_history(
        db,
        timecard=timecard,
        event_type=TimecardHistoryType.SUBMITTED,
        actor_user_id=actor_user_id,
        details={"approval_required": approval_required, "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.timecard.submitted",
        target_type="timecard",
        target_id=str(timecard.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": timecard.status.value, "revision": timecard.revision},
    )
    await _publish_timecard_change(
        db,
        timecard=timecard,
        event_type="workforce.timecard.submitted",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return timecard


async def review_timecard(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    timecard_id: UUID,
    expected_revision: int,
    approve: bool,
    actor_user_id: UUID,
    permission_keys: set[str],
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Timecard:
    timecard = await _load_timecard_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        timecard_id=timecard_id,
        expected_revision=expected_revision,
    )
    if timecard.status != TimecardStatus.IN_REVIEW:
        raise WorkforceValidationError("Only a timecard in review can be approved or rejected")
    if timecard.workflow_instance_id is None:
        raise WorkforceValidationError("Timecard approval must use the shared Workflow engine")

    config = await _effective_time_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    config_key = (
        "workforce.timecards.workflow.approve_transition_key"
        if approve
        else "workforce.timecards.workflow.reject_transition_key"
    )
    transition_key = str(_setting(config, config_key, "")).strip()
    if not transition_key:
        raise WorkforceValidationError(f"Shared workflow transition is not configured: {config_key}")

    workflow = await db.get(WorkflowInstance, timecard.workflow_instance_id)
    if workflow is None:
        raise WorkforceValidationError("Timecard workflow instance was not found")
    try:
        workflow = await execute_transition(
            db,
            workflow_instance_id=workflow.id,
            organization_id=organization_id,
            transition_key=transition_key,
            expected_instance_version=workflow.version,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            reason=reason,
            session_id=session_id,
            conditions_satisfied=True,
            approval_completed=True,
        )
    except WorkflowValidationError as exc:
        raise WorkforceValidationError(str(exc)) from exc

    now = datetime.now(UTC)
    history_type: TimecardHistoryType
    action: str
    if approve:
        if workflow.status != WorkflowInstanceStatus.COMPLETED:
            raise WorkforceValidationError(
                "Configured approval transition must complete the workflow before the timecard can be approved"
            )
        timecard.status = TimecardStatus.APPROVED
        timecard.approved_at = now
        history_type = TimecardHistoryType.APPROVED
        action = "workforce.timecard.approved"
    else:
        timecard.status = TimecardStatus.REJECTED
        timecard.rejected_at = now
        history_type = TimecardHistoryType.REJECTED
        action = "workforce.timecard.rejected"

    timecard.revision += 1
    await db.flush()
    await _timecard_history(
        db,
        timecard=timecard,
        event_type=history_type,
        actor_user_id=actor_user_id,
        details={"reason": reason, "workflow_instance_version": workflow.version},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=action,
        target_type="timecard",
        target_id=str(timecard.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": timecard.status.value, "revision": timecard.revision},
    )
    await _publish_timecard_change(
        db,
        timecard=timecard,
        event_type=action,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return timecard
