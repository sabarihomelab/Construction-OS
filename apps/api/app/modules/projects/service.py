from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.authorization.models import OrganizationAuthorizationState, Role
from app.modules.events.service import enqueue_event
from app.modules.identity.models import MembershipStatus, OrganizationMembership
from app.modules.projects.models import (
    Project,
    ProjectMembership,
    ProjectMembershipStatus,
    ProjectRoleAssignment,
)
from app.modules.search.service import schedule_search_index


class ProjectValidationError(ValueError):
    pass


class ProjectConflictError(ValueError):
    pass


async def _bump_authorization_revision(db: AsyncSession, organization_id: UUID) -> int:
    state = await db.get(OrganizationAuthorizationState, organization_id)
    if state is None:
        state = OrganizationAuthorizationState(organization_id=organization_id, revision=2)
        db.add(state)
    else:
        state.revision += 1
    await db.flush()
    return state.revision


def _project_changes(project: Project) -> dict[str, object]:
    return {
        "number": project.number,
        "name": project.name,
        "status": project.status.value,
        "revision": project.revision,
        "timezone": project.timezone,
        "currency_code": project.currency_code,
        "unit_system": project.unit_system,
        "start_date": project.start_date,
        "target_completion_date": project.target_completion_date,
        "country_code": project.country_code,
    }


async def create_project(
    db: AsyncSession,
    *,
    organization_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> Project:
    number = str(values.get("number") or "").strip()
    name = str(values.get("name") or "").strip()
    if not number or not name:
        raise ProjectValidationError("Project number and name are required")

    existing = await db.scalar(
        select(Project.id).where(
            Project.organization_id == organization_id,
            Project.number == number,
        )
    )
    if existing is not None:
        raise ProjectConflictError("Project number already exists in this company")

    data = dict(values)
    data.pop("organization_id", None)
    data["number"] = number
    data["name"] = name
    if data.get("currency_code"):
        data["currency_code"] = str(data["currency_code"]).upper()
    if data.get("country_code"):
        data["country_code"] = str(data["country_code"]).upper()
    if (
        data.get("target_completion_date")
        and data.get("start_date")
        and data["target_completion_date"] < data["start_date"]
    ):
        raise ProjectValidationError("Target completion date cannot be before start date")

    project = Project(organization_id=organization_id, **data)
    db.add(project)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="project.created",
        target_type="project",
        target_id=str(project.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        changes={"after": _project_changes(project)},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="project.created",
        entity_type="project",
        entity_id=project.id,
        entity_version=project.revision,
        required_permission_key="projects.project.view",
        scope_type="project",
        scope_id=project.id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"revision": project.revision},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="project",
        entity_id=project.id,
        entity_version=project.revision,
        correlation_id=correlation_id,
    )
    return project


async def update_project(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
) -> Project:
    project = await db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.organization_id == organization_id)
        .with_for_update()
    )
    if project is None:
        raise ProjectValidationError("Project was not found")
    if project.revision != expected_revision:
        raise ProjectConflictError(
            f"Project changed from revision {expected_revision} to {project.revision}; refresh before saving"
        )

    before = _project_changes(project)
    mutable = {
        "number",
        "name",
        "description",
        "status",
        "timezone",
        "currency_code",
        "unit_system",
        "start_date",
        "target_completion_date",
        "address_line_1",
        "address_line_2",
        "locality",
        "region",
        "postal_code",
        "country_code",
    }
    for key, value in changes.items():
        if key not in mutable:
            continue
        if key in {"number", "name"}:
            if not isinstance(value, str) or not value.strip():
                raise ProjectValidationError(f"Project {key} cannot be empty")
            value = value.strip()
        if key == "number" and value != project.number:
            existing = await db.scalar(
                select(Project.id).where(
                    Project.organization_id == organization_id,
                    Project.number == value,
                    Project.id != project.id,
                )
            )
            if existing is not None:
                raise ProjectConflictError("Project number already exists in this company")
        if key == "currency_code" and isinstance(value, str):
            value = value.upper()
        if key == "country_code" and isinstance(value, str):
            value = value.upper()
        setattr(project, key, value)

    if (
        project.target_completion_date
        and project.start_date
        and project.target_completion_date < project.start_date
    ):
        raise ProjectValidationError("Target completion date cannot be before start date")

    project.revision += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="project.updated",
        target_type="project",
        target_id=str(project.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": before, "after": _project_changes(project)},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="project.updated",
        entity_type="project",
        entity_id=project.id,
        entity_version=project.revision,
        required_permission_key="projects.project.view",
        scope_type="project",
        scope_id=project.id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"revision": project.revision},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="project",
        entity_id=project.id,
        entity_version=project.revision,
        correlation_id=correlation_id,
    )
    return project


async def add_project_member(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    organization_membership_id: UUID,
    actor_user_id: UUID,
    title: str | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> ProjectMembership:
    project = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise ProjectValidationError("Project was not found")

    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == organization_membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise ProjectValidationError("An active company membership is required")

    normalized_title = title.strip() if title and title.strip() else None
    row = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == organization_membership_id,
        )
    )
    changed = False
    if row is None:
        row = ProjectMembership(
            organization_id=organization_id,
            project_id=project_id,
            organization_membership_id=organization_membership_id,
            title=normalized_title,
        )
        db.add(row)
        changed = True
    else:
        if row.status != ProjectMembershipStatus.ACTIVE:
            row.status = ProjectMembershipStatus.ACTIVE
            changed = True
        if normalized_title is not None and row.title != normalized_title:
            row.title = normalized_title
            changed = True

    if not changed:
        return row

    revision = await _bump_authorization_revision(db, organization_id)
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="project.membership.added",
        target_type="project_membership",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.HIGH,
        changes={
            "project_id": str(project_id),
            "organization_membership_id": str(organization_membership_id),
            "status": row.status.value,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="access_context.changed",
        entity_type="organization_membership",
        entity_id=organization_membership_id,
        entity_version=revision,
        recipient_membership_id=organization_membership_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"authorization_revision": revision},
    )
    return row


async def assign_project_role(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_membership_id: UUID,
    role_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> ProjectRoleAssignment:
    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.id == project_membership_id,
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise ProjectValidationError("Active project membership was not found")

    role = await db.scalar(
        select(Role).where(
            Role.id == role_id,
            Role.organization_id == organization_id,
            Role.is_active.is_(True),
        )
    )
    if role is None:
        raise ProjectValidationError("Active company role was not found")

    assignment = await db.scalar(
        select(ProjectRoleAssignment).where(
            ProjectRoleAssignment.project_membership_id == project_membership_id,
            ProjectRoleAssignment.role_id == role_id,
        )
    )
    if assignment is not None:
        return assignment

    assignment = ProjectRoleAssignment(
        organization_id=organization_id,
        project_membership_id=project_membership_id,
        role_id=role_id,
    )
    db.add(assignment)

    revision = await _bump_authorization_revision(db, organization_id)
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="project.role.assigned",
        target_type="project_membership",
        target_id=str(project_membership_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.HIGH,
        changes={"role_id": str(role_id), "project_id": str(membership.project_id)},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="access_context.changed",
        entity_type="organization_membership",
        entity_id=membership.organization_membership_id,
        entity_version=revision,
        recipient_membership_id=membership.organization_membership_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"authorization_revision": revision},
    )
    return assignment


async def set_project_membership_status(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_membership_id: UUID,
    status: ProjectMembershipStatus,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectMembership:
    membership = await db.scalar(
        select(ProjectMembership)
        .where(
            ProjectMembership.id == project_membership_id,
            ProjectMembership.organization_id == organization_id,
        )
        .with_for_update()
    )
    if membership is None:
        raise ProjectValidationError("Project membership was not found")
    if membership.status == status:
        return membership

    previous = membership.status
    membership.status = status
    revision = await _bump_authorization_revision(db, organization_id)
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="project.membership.status.changed",
        target_type="project_membership",
        target_id=str(membership.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"before": previous.value, "after": status.value},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="access_context.changed",
        entity_type="organization_membership",
        entity_id=membership.organization_membership_id,
        entity_version=revision,
        recipient_membership_id=membership.organization_membership_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"authorization_revision": revision},
    )
    return membership
