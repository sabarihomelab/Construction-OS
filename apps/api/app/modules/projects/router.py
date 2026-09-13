from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.authorization.models import Role
from app.modules.features.schemas import AccessContext
from app.modules.features.service import build_access_context
from app.modules.identity.models import OrganizationMembership, User
from app.modules.projects.models import Project, ProjectMembership, ProjectRoleAssignment
from app.modules.projects.schemas import (
    ProjectAccessMembershipRead,
    ProjectAccessRoleRead,
    ProjectCreate,
    ProjectMembershipCreate,
    ProjectMembershipRead,
    ProjectMembershipStatusUpdate,
    ProjectRead,
    ProjectRoleAssignmentCreate,
    ProjectRoleAssignmentRead,
    ProjectRoleSet,
    ProjectUpdate,
)
from app.modules.projects.service import (
    ProjectConflictError,
    ProjectValidationError,
    add_project_member,
    assign_project_role,
    create_project,
    replace_project_roles,
    set_project_membership_status,
    update_project,
)
from app.modules.sessions.deps import CurrentSession

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_permissions(context: AccessContext, project_id: UUID) -> set[str]:
    return set(context.permissions) | set(context.project_permissions.get(str(project_id), []))


def _require_organization_permission(context: AccessContext, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _require_project_permission(
    context: AccessContext,
    project_id: UUID,
    permission_key: str,
) -> None:
    if permission_key not in _project_permissions(context, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


async def _load_project_or_404(db: DbSession, context: AccessContext, project_id: UUID) -> Project:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == context.organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _project_access_item(
    db: DbSession,
    *,
    organization_id: UUID,
    membership: ProjectMembership,
) -> ProjectAccessMembershipRead:
    company_membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership.organization_membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if company_membership is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project membership is missing its company membership",
        )
    user = await db.get(User, company_membership.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project membership is missing its user",
        )
    roles = list(
        (
            await db.scalars(
                select(Role)
                .join(ProjectRoleAssignment, ProjectRoleAssignment.role_id == Role.id)
                .where(
                    ProjectRoleAssignment.project_membership_id == membership.id,
                    ProjectRoleAssignment.organization_id == organization_id,
                    Role.organization_id == organization_id,
                )
                .order_by(Role.name, Role.key)
            )
        ).all()
    )
    role_reads = [
        ProjectAccessRoleRead(
            id=role.id,
            key=role.key,
            name=role.name,
            assignment_scope=role.assignment_scope,
            is_template=role.is_template,
            is_protected=role.is_protected,
        )
        for role in roles
    ]
    return ProjectAccessMembershipRead(
        id=membership.id,
        organization_membership_id=membership.organization_membership_id,
        user_id=user.id,
        display_name=user.display_name,
        primary_email=user.primary_email,
        membership_kind=company_membership.kind,
        status=membership.status,
        title=membership.title,
        role_ids=[role.id for role in roles],
        roles=role_reads,
    )


@router.get("", response_model=list[ProjectRead])
async def list_projects(db: DbSession, session: CurrentSession) -> list[Project]:
    context = await build_access_context(db, session.membership_id)
    statement = select(Project).where(Project.organization_id == context.organization_id)
    if "projects.project.view" not in context.permissions:
        project_ids = [
            UUID(project_id)
            for project_id, permissions in context.project_permissions.items()
            if "projects.project.view" in permissions
        ]
        if not project_ids:
            return []
        statement = statement.where(Project.id.in_(project_ids))
    rows = await db.scalars(statement.order_by(Project.name, Project.id))
    return list(rows.all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project_route(
    payload: ProjectCreate,
    db: DbSession,
    session: CurrentSession,
) -> Project:
    context = await build_access_context(db, session.membership_id)
    _require_organization_permission(context, "projects.project.create")
    try:
        project = await create_project(
            db,
            organization_id=context.organization_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(project)
        return project
    except ProjectConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProjectValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> Project:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.project.view")
    return await _load_project_or_404(db, context, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
async def patch_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: DbSession,
    session: CurrentSession,
) -> Project:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.project.update")
    if payload.status is not None and payload.status.value in {"closeout", "complete", "archived"}:
        _require_project_permission(context, project_id, "projects.project.archive")

    changes = payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True)
    try:
        project = await update_project(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            expected_revision=payload.expected_revision,
            changes=changes,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(project)
        return project
    except ProjectConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProjectValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{project_id}/memberships", response_model=list[ProjectMembershipRead])
async def list_project_memberships(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectMembership]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.membership.view")
    await _load_project_or_404(db, context, project_id)
    rows = await db.scalars(
        select(ProjectMembership)
        .where(
            ProjectMembership.organization_id == context.organization_id,
            ProjectMembership.project_id == project_id,
        )
        .order_by(ProjectMembership.created_at, ProjectMembership.id)
    )
    return list(rows.all())


@router.get("/{project_id}/access", response_model=list[ProjectAccessMembershipRead])
async def list_project_access(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectAccessMembershipRead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.membership.view")
    await _load_project_or_404(db, context, project_id)
    memberships = list(
        (
            await db.scalars(
                select(ProjectMembership)
                .where(
                    ProjectMembership.organization_id == context.organization_id,
                    ProjectMembership.project_id == project_id,
                )
                .order_by(ProjectMembership.created_at, ProjectMembership.id)
            )
        ).all()
    )
    return [
        await _project_access_item(
            db,
            organization_id=context.organization_id,
            membership=membership,
        )
        for membership in memberships
    ]


@router.post(
    "/{project_id}/memberships",
    response_model=ProjectMembershipRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_membership(
    project_id: UUID,
    payload: ProjectMembershipCreate,
    db: DbSession,
    session: CurrentSession,
) -> ProjectMembership:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.membership.manage")
    try:
        membership = await add_project_member(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            organization_membership_id=payload.organization_membership_id,
            actor_user_id=session.user_id,
            title=payload.title,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(membership)
        return membership
    except ProjectValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch(
    "/{project_id}/memberships/{project_membership_id}",
    response_model=ProjectMembershipRead,
)
async def patch_project_membership(
    project_id: UUID,
    project_membership_id: UUID,
    payload: ProjectMembershipStatusUpdate,
    db: DbSession,
    session: CurrentSession,
) -> ProjectMembership:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.membership.manage")
    try:
        membership = await set_project_membership_status(
            db,
            organization_id=context.organization_id,
            project_membership_id=project_membership_id,
            status=payload.status,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        if membership.project_id != project_id:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found")
        await db.commit()
        await db.refresh(membership)
        return membership
    except ProjectValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{project_id}/memberships/{project_membership_id}/roles",
    response_model=ProjectRoleAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_role_assignment(
    project_id: UUID,
    project_membership_id: UUID,
    payload: ProjectRoleAssignmentCreate,
    db: DbSession,
    session: CurrentSession,
):
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.membership.manage")
    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.id == project_membership_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_id == context.organization_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found")
    try:
        assignment = await assign_project_role(
            db,
            organization_id=context.organization_id,
            project_membership_id=project_membership_id,
            role_id=payload.role_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(assignment)
        return assignment
    except ProjectValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put(
    "/{project_id}/memberships/{project_membership_id}/roles",
    response_model=ProjectAccessMembershipRead,
)
async def put_project_role_assignments(
    project_id: UUID,
    project_membership_id: UUID,
    payload: ProjectRoleSet,
    db: DbSession,
    session: CurrentSession,
) -> ProjectAccessMembershipRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "projects.membership.manage")
    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.id == project_membership_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_id == context.organization_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found")
    try:
        await replace_project_roles(
            db,
            organization_id=context.organization_id,
            project_membership_id=project_membership_id,
            role_ids=set(payload.role_ids),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        return await _project_access_item(
            db,
            organization_id=context.organization_id,
            membership=membership,
        )
    except ProjectValidationError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
