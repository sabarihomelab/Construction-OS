from collections.abc import Mapping
from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.workforce.models import ProjectWorkerAssignment, ProjectWorkerRate
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError


async def create_project_worker_rate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectWorkerRate:
    assignment = await db.scalar(
        select(ProjectWorkerAssignment).where(
            ProjectWorkerAssignment.id == assignment_id,
            ProjectWorkerAssignment.organization_id == organization_id,
            ProjectWorkerAssignment.project_id == project_id,
        )
    )
    if assignment is None:
        raise WorkforceValidationError("Project Worker assignment was not found")

    data = dict(values)
    effective_from = data["effective_from"]
    effective_to = data.get("effective_to")
    if assignment.start_date and effective_from < assignment.start_date:
        raise WorkforceValidationError("Rate cannot start before the project assignment")
    if assignment.end_date and effective_to and effective_to > assignment.end_date:
        raise WorkforceValidationError("Rate cannot end after the project assignment")
    if assignment.end_date and effective_from > assignment.end_date:
        raise WorkforceValidationError("Rate cannot start after the project assignment ended")

    overlap_conditions = [
        ProjectWorkerRate.organization_id == organization_id,
        ProjectWorkerRate.assignment_id == assignment_id,
        or_(
            ProjectWorkerRate.effective_to.is_(None),
            ProjectWorkerRate.effective_to >= effective_from,
        ),
    ]
    if effective_to is not None:
        overlap_conditions.append(ProjectWorkerRate.effective_from <= effective_to)

    overlapping = await db.scalar(select(ProjectWorkerRate.id).where(and_(*overlap_conditions)))
    if overlapping is not None:
        raise WorkforceConflictError("A Worker rate already covers part of this effective period")

    rate = ProjectWorkerRate(
        organization_id=organization_id,
        project_id=project_id,
        assignment_id=assignment_id,
        worker_id=assignment.worker_id,
        **data,
    )
    db.add(rate)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.project_worker_rate.created",
        target_type="project_worker_rate",
        target_id=str(rate.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "worker_id": str(rate.worker_id),
            "wage_basis": rate.wage_basis.value,
            "effective_from": rate.effective_from,
            "effective_to": rate.effective_to,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workforce.project_worker_rate.changed",
        entity_type="project_worker_rate",
        entity_id=rate.id,
        entity_version=rate.revision,
        required_permission_key="workforce.rate.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"worker_id": str(rate.worker_id), "effective_from": str(rate.effective_from)},
    )
    return rate


async def end_project_worker_rate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    rate_id: UUID,
    expected_revision: int,
    effective_to: date,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectWorkerRate:
    rate = await db.scalar(
        select(ProjectWorkerRate)
        .where(
            ProjectWorkerRate.id == rate_id,
            ProjectWorkerRate.organization_id == organization_id,
            ProjectWorkerRate.project_id == project_id,
            ProjectWorkerRate.assignment_id == assignment_id,
        )
        .with_for_update()
    )
    if rate is None:
        raise WorkforceValidationError("Project Worker rate was not found")
    if rate.revision != expected_revision:
        raise WorkforceConflictError("Project Worker rate changed; refresh before saving")
    if effective_to < rate.effective_from:
        raise WorkforceValidationError("Rate end date cannot be before its start date")
    if rate.effective_to == effective_to:
        return rate

    next_rate = await db.scalar(
        select(ProjectWorkerRate.id).where(
            ProjectWorkerRate.organization_id == organization_id,
            ProjectWorkerRate.assignment_id == assignment_id,
            ProjectWorkerRate.id != rate.id,
            ProjectWorkerRate.effective_from <= effective_to,
            or_(
                ProjectWorkerRate.effective_to.is_(None),
                ProjectWorkerRate.effective_to >= rate.effective_from,
            ),
        )
    )
    if next_rate is not None:
        raise WorkforceConflictError("Rate end date would overlap another Worker rate")

    previous_end = rate.effective_to
    rate.effective_to = effective_to
    rate.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.project_worker_rate.ended",
        target_type="project_worker_rate",
        target_id=str(rate.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"before": {"effective_to": previous_end}, "after": {"effective_to": effective_to}},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workforce.project_worker_rate.changed",
        entity_type="project_worker_rate",
        entity_id=rate.id,
        entity_version=rate.revision,
        required_permission_key="workforce.rate.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"worker_id": str(rate.worker_id), "effective_to": str(rate.effective_to)},
    )
    return rate
