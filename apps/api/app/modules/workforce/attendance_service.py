from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import RecordStatus, WBSCode
from app.modules.configuration.schemas import EffectiveConfigurationRead
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.events.service import enqueue_event
from app.modules.projects.models import Project
from app.modules.workflows.models import WorkflowInstance
from app.modules.workflows.service import WorkflowValidationError, execute_transition, start_workflow_instance
from app.modules.workforce.attendance_models import (
    AttendanceEntry,
    AttendanceHistoryEvent,
    AttendanceHistoryType,
    AttendanceMarkStatus,
    AttendanceRegister,
    AttendanceRegisterStatus,
)
from app.modules.workforce.models import (
    ProjectWorkerAssignment,
    ProjectWorkerAssignmentStatus,
    Worker,
)
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError


def _setting(config: EffectiveConfigurationRead, key: str, default: object) -> object:
    for setting in config.settings:
        if setting.key == key:
            return setting.value
    return default


async def _effective_config(
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


async def _load_register_for_update(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    register_id: UUID,
    expected_revision: int,
) -> AttendanceRegister:
    register = await db.scalar(
        select(AttendanceRegister)
        .where(
            AttendanceRegister.id == register_id,
            AttendanceRegister.organization_id == organization_id,
            AttendanceRegister.project_id == project_id,
        )
        .with_for_update()
    )
    if register is None:
        raise WorkforceValidationError("Attendance register was not found")
    if register.revision != expected_revision:
        raise WorkforceConflictError(
            f"Attendance register changed from revision {expected_revision} to {register.revision}; refresh before saving"
        )
    return register


async def _history(
    db: AsyncSession,
    *,
    register: AttendanceRegister,
    event_type: AttendanceHistoryType,
    actor_user_id: UUID,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AttendanceHistoryEvent(
            organization_id=register.organization_id,
            register_id=register.id,
            event_type=event_type,
            register_revision=register.revision,
            actor_user_id=actor_user_id,
            details=details or {},
        )
    )


async def _publish(
    db: AsyncSession,
    *,
    register: AttendanceRegister,
    event_type: str,
    actor_user_id: UUID,
    session_id: UUID | None,
    extra: dict[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "attendance_date": register.attendance_date.isoformat(),
        "shift_code": register.shift_code,
        "status": register.status.value,
        "revision": register.revision,
    }
    payload.update(extra or {})
    await enqueue_event(
        db,
        organization_id=register.organization_id,
        event_type=event_type,
        entity_type="attendance_register",
        entity_id=register.id,
        entity_version=register.revision,
        required_permission_key="workforce.attendance.view",
        scope_type="project",
        scope_id=register.project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload=payload,
    )


async def _active_assignments(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    attendance_date,
) -> list[ProjectWorkerAssignment]:
    rows = await db.scalars(
        select(ProjectWorkerAssignment)
        .where(
            ProjectWorkerAssignment.organization_id == organization_id,
            ProjectWorkerAssignment.project_id == project_id,
            ProjectWorkerAssignment.status == ProjectWorkerAssignmentStatus.ACTIVE,
            (ProjectWorkerAssignment.start_date.is_(None))
            | (ProjectWorkerAssignment.start_date <= attendance_date),
            (ProjectWorkerAssignment.end_date.is_(None))
            | (ProjectWorkerAssignment.end_date >= attendance_date),
        )
        .order_by(ProjectWorkerAssignment.created_at, ProjectWorkerAssignment.id)
    )
    return list(rows.all())


async def _entry_for_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    register_id: UUID,
    assignment: ProjectWorkerAssignment,
    mark_status: AttendanceMarkStatus = AttendanceMarkStatus.NOT_MARKED,
    regular_hours: Decimal = Decimal(0),
    overtime_hours: Decimal = Decimal(0),
    wbs_code_id: UUID | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> AttendanceEntry:
    worker = await db.scalar(
        select(Worker).where(
            Worker.id == assignment.worker_id,
            Worker.organization_id == organization_id,
        )
    )
    if worker is None:
        raise WorkforceValidationError("Assigned Worker was not found")
    snapshot = {
        "worker_number": worker.worker_number,
        "worker_name": " ".join(part for part in (worker.first_name, worker.last_name) if part),
        "project_role": assignment.project_role,
        "trade": assignment.trade or worker.trade,
        "crew_id": str(assignment.crew_id) if assignment.crew_id else None,
        "employer_party_id": str(assignment.employer_party_id) if assignment.employer_party_id else None,
        "engagement_type": assignment.engagement_type.value if assignment.engagement_type else None,
        "assignment_revision": assignment.revision,
    }
    return AttendanceEntry(
        organization_id=organization_id,
        project_id=project_id,
        register_id=register_id,
        assignment_id=assignment.id,
        worker_id=assignment.worker_id,
        crew_id=assignment.crew_id,
        employer_party_id=assignment.employer_party_id,
        engagement_type=assignment.engagement_type,
        trade=assignment.trade or worker.trade,
        wbs_code_id=wbs_code_id,
        mark_status=mark_status,
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
        location=location,
        notes=notes,
        context_snapshot=snapshot,
    )


async def create_attendance_register(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    attendance_date,
    shift_code: str,
    notes: str | None,
    populate_active_workers: bool,
    session_id: UUID | None = None,
) -> AttendanceRegister:
    project = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise WorkforceValidationError("Project was not found")
    normalized_shift = shift_code.strip()
    if not normalized_shift:
        raise WorkforceValidationError("Shift is required")
    duplicate = await db.scalar(
        select(AttendanceRegister.id).where(
            AttendanceRegister.organization_id == organization_id,
            AttendanceRegister.project_id == project_id,
            AttendanceRegister.attendance_date == attendance_date,
            AttendanceRegister.shift_code == normalized_shift,
        )
    )
    if duplicate is not None:
        raise WorkforceConflictError("Attendance register already exists for this project, date and shift")

    register = AttendanceRegister(
        organization_id=organization_id,
        project_id=project_id,
        attendance_date=attendance_date,
        shift_code=normalized_shift,
        prepared_by_membership_id=membership_id,
        notes=notes.strip() if notes else None,
    )
    db.add(register)
    await db.flush()
    populated = 0
    if populate_active_workers:
        for assignment in await _active_assignments(
            db,
            organization_id=organization_id,
            project_id=project_id,
            attendance_date=attendance_date,
        ):
            db.add(
                await _entry_for_assignment(
                    db,
                    organization_id=organization_id,
                    project_id=project_id,
                    register_id=register.id,
                    assignment=assignment,
                )
            )
            populated += 1
        if populated:
            register.revision += 1
    await db.flush()
    await _history(
        db,
        register=register,
        event_type=AttendanceHistoryType.CREATED,
        actor_user_id=actor_user_id,
        details={"populated_workers": populated},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.attendance.created",
        target_type="attendance_register",
        target_id=str(register.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={
            "project_id": str(project_id),
            "attendance_date": attendance_date,
            "shift_code": normalized_shift,
            "populated_workers": populated,
        },
    )
    await _publish(
        db,
        register=register,
        event_type="workforce.attendance.created",
        actor_user_id=actor_user_id,
        session_id=session_id,
        extra={"entry_count": populated},
    )
    return register


async def replace_attendance_entries(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    register_id: UUID,
    expected_revision: int,
    entries: list[dict[str, object]],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> AttendanceRegister:
    register = await _load_register_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        register_id=register_id,
        expected_revision=expected_revision,
    )
    if register.status not in {AttendanceRegisterStatus.DRAFT, AttendanceRegisterStatus.REJECTED}:
        raise WorkforceValidationError("Only draft or rejected attendance registers can be edited")
    config = await _effective_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    require_wbs = bool(_setting(config, "workforce.attendance.require_wbs", False))
    max_daily_hours = Decimal(str(_setting(config, "workforce.timecards.max_daily_hours", "24")))
    seen_assignments: set[UUID] = set()
    prepared: list[AttendanceEntry] = []
    active = {
        row.id: row
        for row in await _active_assignments(
            db,
            organization_id=organization_id,
            project_id=project_id,
            attendance_date=register.attendance_date,
        )
    }
    for raw in entries:
        assignment_id = UUID(str(raw["assignment_id"]))
        if assignment_id in seen_assignments:
            raise WorkforceValidationError("The same Worker assignment cannot be marked twice")
        seen_assignments.add(assignment_id)
        assignment = active.get(assignment_id)
        if assignment is None:
            raise WorkforceValidationError("Attendance can only be marked for an active assignment on this date")
        mark_status = AttendanceMarkStatus(str(raw["mark_status"]))
        regular_hours = Decimal(str(raw.get("regular_hours") or 0))
        overtime_hours = Decimal(str(raw.get("overtime_hours") or 0))
        if regular_hours < 0 or overtime_hours < 0:
            raise WorkforceValidationError("Attendance hours cannot be negative")
        if regular_hours + overtime_hours > max_daily_hours:
            raise WorkforceValidationError(
                f"Attendance exceeds configured maximum daily hours ({max_daily_hours})"
            )
        if mark_status in {
            AttendanceMarkStatus.NOT_MARKED,
            AttendanceMarkStatus.ABSENT,
            AttendanceMarkStatus.LEAVE,
            AttendanceMarkStatus.WEEKLY_OFF,
        } and (regular_hours or overtime_hours):
            raise WorkforceValidationError("Non-working attendance marks cannot contain work hours")
        wbs_code_id = raw.get("wbs_code_id")
        if wbs_code_id is not None:
            wbs_code_id = UUID(str(wbs_code_id))
            wbs = await db.scalar(
                select(WBSCode.id).where(
                    WBSCode.id == wbs_code_id,
                    WBSCode.organization_id == organization_id,
                    WBSCode.project_id == project_id,
                    WBSCode.status == RecordStatus.ACTIVE,
                )
            )
            if wbs is None:
                raise WorkforceValidationError("Attendance WBS/Cost Code was not found or is inactive")
        if require_wbs and mark_status in {AttendanceMarkStatus.PRESENT, AttendanceMarkStatus.HALF_DAY} and wbs_code_id is None:
            raise WorkforceValidationError("WBS/Cost Code is required for working attendance marks")
        prepared.append(
            await _entry_for_assignment(
                db,
                organization_id=organization_id,
                project_id=project_id,
                register_id=register.id,
                assignment=assignment,
                mark_status=mark_status,
                regular_hours=regular_hours,
                overtime_hours=overtime_hours,
                wbs_code_id=wbs_code_id,
                location=str(raw.get("location") or "").strip() or None,
                notes=str(raw.get("notes") or "").strip() or None,
            )
        )

    await db.execute(
        delete(AttendanceEntry).where(
            AttendanceEntry.organization_id == organization_id,
            AttendanceEntry.register_id == register.id,
        )
    )
    for entry in prepared:
        db.add(entry)
    register.revision += 1
    if register.status == AttendanceRegisterStatus.REJECTED:
        register.status = AttendanceRegisterStatus.DRAFT
        register.rejected_at = None
    await db.flush()
    await _history(
        db,
        register=register,
        event_type=AttendanceHistoryType.UPDATED,
        actor_user_id=actor_user_id,
        details={"entry_count": len(prepared), "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.attendance.entries.updated",
        target_type="attendance_register",
        target_id=str(register.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"entry_count": len(prepared), "revision": register.revision},
    )
    await _publish(
        db,
        register=register,
        event_type="workforce.attendance.updated",
        actor_user_id=actor_user_id,
        session_id=session_id,
        extra={"entry_count": len(prepared)},
    )
    return register


async def submit_attendance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    register_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    permission_keys: set[str],
    session_id: UUID | None = None,
    reason: str | None = None,
) -> AttendanceRegister:
    register = await _load_register_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        register_id=register_id,
        expected_revision=expected_revision,
    )
    if register.status not in {AttendanceRegisterStatus.DRAFT, AttendanceRegisterStatus.REJECTED}:
        raise WorkforceValidationError("Only draft or rejected attendance can be submitted")
    entries = list(
        (
            await db.scalars(
                select(AttendanceEntry).where(
                    AttendanceEntry.organization_id == organization_id,
                    AttendanceEntry.register_id == register.id,
                )
            )
        ).all()
    )
    if not entries:
        raise WorkforceValidationError("Attendance register has no Workers")
    if any(entry.mark_status == AttendanceMarkStatus.NOT_MARKED for entry in entries):
        raise WorkforceValidationError("Mark every Worker before submitting attendance")

    config = await _effective_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    approval_required = bool(_setting(config, "workforce.attendance.approval.required", False))
    now = datetime.now(UTC)
    register.submitted_at = now
    register.configuration_context = {
        "configuration_revisions": config.configuration_revisions,
        "project_template_version_id": str(config.project_template_version_id) if config.project_template_version_id else None,
        "approval_required": approval_required,
        "require_wbs": bool(_setting(config, "workforce.attendance.require_wbs", False)),
        "effective_at": now.isoformat(),
    }
    if approval_required:
        workflow_key = str(_setting(config, "workforce.attendance.workflow.definition_key", "")).strip()
        if not workflow_key:
            raise WorkforceValidationError(
                "Attendance approval is enabled but no shared workflow definition is configured"
            )
        if register.workflow_instance_id is None:
            try:
                workflow = await start_workflow_instance(
                    db,
                    organization_id=organization_id,
                    definition_key=workflow_key,
                    entity_type="attendance_register",
                    entity_id=register.id,
                    actor_user_id=actor_user_id,
                )
            except WorkflowValidationError as exc:
                raise WorkforceValidationError(str(exc)) from exc
            register.workflow_instance_id = workflow.id
        elif register.status == AttendanceRegisterStatus.REJECTED:
            transition_key = str(
                _setting(config, "workforce.attendance.workflow.resubmit_transition_key", "")
            ).strip()
            workflow = await db.get(WorkflowInstance, register.workflow_instance_id)
            if not transition_key or workflow is None:
                raise WorkforceValidationError("Rejected attendance has no valid resubmit workflow")
            try:
                await execute_transition(
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
        register.status = AttendanceRegisterStatus.IN_REVIEW
    else:
        register.status = AttendanceRegisterStatus.APPROVED
        register.approved_at = now
        register.approved_by_membership_id = membership_id
    register.rejected_at = None
    register.revision += 1
    await db.flush()
    await _history(
        db,
        register=register,
        event_type=AttendanceHistoryType.SUBMITTED,
        actor_user_id=actor_user_id,
        details={"approval_required": approval_required, "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.attendance.submitted",
        target_type="attendance_register",
        target_id=str(register.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": register.status.value, "revision": register.revision},
    )
    await _publish(
        db,
        register=register,
        event_type=(
            "workforce.attendance.approved"
            if register.status == AttendanceRegisterStatus.APPROVED
            else "workforce.attendance.submitted"
        ),
        actor_user_id=actor_user_id,
        session_id=session_id,
        extra={"entry_count": len(entries)},
    )
    return register


async def review_attendance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    register_id: UUID,
    expected_revision: int,
    approve: bool,
    actor_user_id: UUID,
    permission_keys: set[str],
    session_id: UUID | None = None,
    reason: str | None = None,
) -> AttendanceRegister:
    register = await _load_register_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        register_id=register_id,
        expected_revision=expected_revision,
    )
    if register.status != AttendanceRegisterStatus.IN_REVIEW:
        raise WorkforceValidationError("Attendance is not awaiting review")
    config = await _effective_config(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project_id,
    )
    workflow = await db.get(WorkflowInstance, register.workflow_instance_id) if register.workflow_instance_id else None
    if workflow is None:
        raise WorkforceValidationError("Attendance workflow instance was not found")
    key_name = (
        "workforce.attendance.workflow.approve_transition_key"
        if approve
        else "workforce.attendance.workflow.reject_transition_key"
    )
    transition_key = str(_setting(config, key_name, "")).strip()
    if not transition_key:
        raise WorkforceValidationError("Attendance review transition is not configured")
    try:
        await execute_transition(
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
            approval_completed=approve,
        )
    except WorkflowValidationError as exc:
        raise WorkforceValidationError(str(exc)) from exc
    now = datetime.now(UTC)
    if approve:
        register.status = AttendanceRegisterStatus.APPROVED
        register.approved_at = now
        register.approved_by_membership_id = membership_id
        event_type = AttendanceHistoryType.APPROVED
        audit_action = "workforce.attendance.approved"
    else:
        register.status = AttendanceRegisterStatus.REJECTED
        register.rejected_at = now
        event_type = AttendanceHistoryType.REJECTED
        audit_action = "workforce.attendance.rejected"
    register.revision += 1
    await db.flush()
    await _history(
        db,
        register=register,
        event_type=event_type,
        actor_user_id=actor_user_id,
        details={"reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=audit_action,
        target_type="attendance_register",
        target_id=str(register.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": register.status.value, "revision": register.revision},
    )
    await _publish(
        db,
        register=register,
        event_type=audit_action,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return register


async def build_dpr_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    register_id: UUID,
) -> list[dict[str, object]]:
    register = await db.scalar(
        select(AttendanceRegister).where(
            AttendanceRegister.id == register_id,
            AttendanceRegister.organization_id == organization_id,
            AttendanceRegister.project_id == project_id,
        )
    )
    if register is None:
        raise WorkforceValidationError("Attendance register was not found")
    if register.status != AttendanceRegisterStatus.APPROVED:
        raise WorkforceValidationError("DPR crew summary is available only from approved attendance")
    entries = list(
        (
            await db.scalars(
                select(AttendanceEntry).where(
                    AttendanceEntry.organization_id == organization_id,
                    AttendanceEntry.register_id == register.id,
                )
            )
        ).all()
    )
    grouped: dict[tuple[UUID | None, UUID | None, str | None], dict[str, object]] = defaultdict(
        lambda: {
            "worker_count": 0,
            "present_count": 0,
            "absent_count": 0,
            "regular_hours": Decimal(0),
            "overtime_hours": Decimal(0),
        }
    )
    for entry in entries:
        key = (entry.employer_party_id, entry.crew_id, entry.trade)
        row = grouped[key]
        row["worker_count"] = int(row["worker_count"]) + 1
        if entry.mark_status in {AttendanceMarkStatus.PRESENT, AttendanceMarkStatus.HALF_DAY}:
            row["present_count"] = int(row["present_count"]) + 1
        elif entry.mark_status == AttendanceMarkStatus.ABSENT:
            row["absent_count"] = int(row["absent_count"]) + 1
        row["regular_hours"] = Decimal(row["regular_hours"]) + entry.regular_hours
        row["overtime_hours"] = Decimal(row["overtime_hours"]) + entry.overtime_hours
    return [
        {
            "employer_party_id": employer_party_id,
            "crew_id": crew_id,
            "trade": trade,
            **values,
        }
        for (employer_party_id, crew_id, trade), values in sorted(
            grouped.items(), key=lambda item: (str(item[0][0] or ""), str(item[0][1] or ""), item[0][2] or "")
        )
    ]
