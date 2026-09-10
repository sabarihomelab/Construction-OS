from collections.abc import Mapping
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.workforce.models import (
    Crew,
    CrewMembership,
    CrewStatus,
    EmploymentStatus,
    ProjectWorkerAssignment,
    Worker,
)
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError


async def update_crew(
    db: AsyncSession,
    *,
    organization_id: UUID,
    crew_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Crew:
    crew = await db.scalar(
        select(Crew)
        .where(Crew.id == crew_id, Crew.organization_id == organization_id)
        .with_for_update()
    )
    if crew is None:
        raise WorkforceValidationError("Crew was not found")
    if crew.revision != expected_revision:
        raise WorkforceConflictError(
            f"Crew changed from revision {expected_revision} to {crew.revision}; refresh before saving"
        )

    before = {"name": crew.name, "status": crew.status.value}
    mutable = {"name", "description", "supervisor_worker_id", "status"}
    for key, value in changes.items():
        if key not in mutable:
            continue
        if key == "name":
            value = str(value or "").strip()
            if not value:
                raise WorkforceValidationError("Crew name is required")
        setattr(crew, key, value)

    if crew.supervisor_worker_id is not None:
        supervisor = await db.scalar(
            select(Worker).where(
                Worker.id == crew.supervisor_worker_id,
                Worker.organization_id == organization_id,
            )
        )
        if supervisor is None or supervisor.status != EmploymentStatus.ACTIVE:
            raise WorkforceValidationError("Crew supervisor must be an active company Worker")

    duplicate = await db.scalar(
        select(Crew.id).where(
            Crew.organization_id == organization_id,
            Crew.name == crew.name,
            Crew.id != crew.id,
        )
    )
    if duplicate is not None:
        raise WorkforceConflictError("Crew name already exists")

    crew.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.crew.updated",
        target_type="crew",
        target_id=str(crew.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": before, "after": {"name": crew.name, "status": crew.status.value}},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workforce.crew.updated",
        entity_type="crew",
        entity_id=crew.id,
        entity_version=crew.revision,
        required_permission_key="workforce.crew.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": crew.revision, "status": crew.status.value},
    )
    return crew


async def end_crew_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    crew_id: UUID,
    crew_membership_id: UUID,
    expected_revision: int,
    effective_to: date,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> CrewMembership:
    membership = await db.scalar(
        select(CrewMembership)
        .where(
            CrewMembership.id == crew_membership_id,
            CrewMembership.organization_id == organization_id,
            CrewMembership.crew_id == crew_id,
        )
        .with_for_update()
    )
    if membership is None:
        raise WorkforceValidationError("Crew membership was not found")
    if membership.revision != expected_revision:
        raise WorkforceConflictError(
            "Crew membership changed; refresh before saving"
        )
    if effective_to < membership.effective_from:
        raise WorkforceValidationError("Crew membership end date cannot be before its start date")
    if membership.effective_to == effective_to:
        return membership

    previous_end = membership.effective_to
    membership.effective_to = effective_to
    membership.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.crew.membership.ended",
        target_type="crew_membership",
        target_id=str(membership.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": {"effective_to": previous_end}, "after": {"effective_to": effective_to}},
    )
    return membership


async def update_project_worker_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectWorkerAssignment:
    assignment = await db.scalar(
        select(ProjectWorkerAssignment)
        .where(
            ProjectWorkerAssignment.id == assignment_id,
            ProjectWorkerAssignment.organization_id == organization_id,
            ProjectWorkerAssignment.project_id == project_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise WorkforceValidationError("Project Worker assignment was not found")
    if assignment.revision != expected_revision:
        raise WorkforceConflictError(
            "Project Worker assignment changed; refresh before saving"
        )

    before = {
        "status": assignment.status.value,
        "crew_id": str(assignment.crew_id) if assignment.crew_id else None,
    }
    mutable = {
        "crew_id",
        "project_role",
        "trade",
        "default_cost_code",
        "start_date",
        "end_date",
        "status",
    }
    for key, value in changes.items():
        if key in mutable:
            setattr(assignment, key, value)

    if assignment.crew_id is not None:
        crew = await db.scalar(
            select(Crew).where(
                Crew.id == assignment.crew_id,
                Crew.organization_id == organization_id,
            )
        )
        if crew is None or crew.status != CrewStatus.ACTIVE:
            raise WorkforceValidationError("Assigned crew must be active and belong to the company")
    if assignment.start_date and assignment.end_date and assignment.end_date < assignment.start_date:
        raise WorkforceValidationError("Assignment end date cannot be before start date")

    assignment.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.project_assignment.updated",
        target_type="project_worker_assignment",
        target_id=str(assignment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "before": before,
            "after": {
                "status": assignment.status.value,
                "crew_id": str(assignment.crew_id) if assignment.crew_id else None,
            },
        },
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
        payload={"worker_id": str(assignment.worker_id), "status": assignment.status.value},
    )
    return assignment
