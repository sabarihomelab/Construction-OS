from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import Party, ProjectPartyAssignment
from app.modules.commercial.service import CommercialConflictError, CommercialValidationError
from app.modules.events.service import enqueue_event
from app.modules.projects.models import Project


async def get_party(
    db: AsyncSession,
    *,
    organization_id: UUID,
    party_id: UUID,
) -> Party:
    party = await db.scalar(
        select(Party).where(Party.id == party_id, Party.organization_id == organization_id)
    )
    if party is None:
        raise CommercialValidationError("Party was not found")
    return party


async def list_project_party_assignments(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    party_id: UUID | None = None,
    include_inactive: bool = False,
) -> list[ProjectPartyAssignment]:
    project = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise CommercialValidationError("Project was not found")

    statement = select(ProjectPartyAssignment).where(
        ProjectPartyAssignment.organization_id == organization_id,
        ProjectPartyAssignment.project_id == project_id,
    )
    if party_id is not None:
        statement = statement.where(ProjectPartyAssignment.party_id == party_id)
    if not include_inactive:
        statement = statement.where(ProjectPartyAssignment.active.is_(True))
    rows = await db.scalars(statement.order_by(ProjectPartyAssignment.role, ProjectPartyAssignment.created_at))
    return list(rows.all())


async def set_project_party_assignment_active(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    expected_updated_at: datetime,
    active: bool,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectPartyAssignment:
    assignment = await db.scalar(
        select(ProjectPartyAssignment)
        .where(
            ProjectPartyAssignment.id == assignment_id,
            ProjectPartyAssignment.organization_id == organization_id,
            ProjectPartyAssignment.project_id == project_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise CommercialValidationError("Project party assignment was not found")
    if assignment.updated_at != expected_updated_at:
        raise CommercialConflictError("Project party assignment changed; refresh before saving")
    if assignment.active == active:
        return assignment

    before = assignment.active
    assignment.active = active
    await db.flush()

    action = "commercial.project_party.reactivated" if active else "commercial.project_party.deactivated"
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=action,
        target_type="project_party_assignment",
        target_id=str(assignment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "before": {"active": before},
            "after": {
                "active": assignment.active,
                "party_id": str(assignment.party_id),
                "project_id": str(assignment.project_id),
                "role": assignment.role.value,
            },
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=action,
        entity_type="project_party_assignment",
        entity_id=assignment.id,
        entity_version=1,
        required_permission_key="commercial.party.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "party_id": str(assignment.party_id),
            "active": assignment.active,
            "role": assignment.role.value,
        },
    )
    return assignment
