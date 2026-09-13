from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.models import Permission, Role, RolePermission
from app.modules.projects.models import (
    ProjectMembership,
    ProjectMembershipStatus,
    ProjectRoleAssignment,
)


async def load_project_permissions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    organization_membership_id: UUID,
) -> dict[str, set[str]]:
    rows = await db.execute(
        select(ProjectMembership.project_id, RolePermission.permission_key)
        .join(
            ProjectRoleAssignment,
            ProjectRoleAssignment.project_membership_id == ProjectMembership.id,
        )
        .join(Role, Role.id == ProjectRoleAssignment.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.key == RolePermission.permission_key)
        .where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.organization_membership_id == organization_membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
            ProjectRoleAssignment.organization_id == organization_id,
            Role.organization_id == organization_id,
            Role.is_active.is_(True),
            Permission.is_active.is_(True),
        )
        .distinct()
        .order_by(ProjectMembership.project_id, RolePermission.permission_key)
    )
    permissions: dict[str, set[str]] = defaultdict(set)
    for project_id, permission_key in rows.all():
        permissions[str(project_id)].add(permission_key)
    return dict(permissions)


def visible_project_scope(
    organization_permissions: set[str],
    project_permissions: dict[str, set[str]],
) -> set[str]:
    if "projects.project.view" in organization_permissions:
        return {"*"}
    return {
        project_id
        for project_id, permission_keys in project_permissions.items()
        if "projects.project.view" in permission_keys
    }


def effective_project_permissions(
    *,
    project_id: UUID | str,
    organization_permissions: set[str],
    project_permissions: dict[str, set[str]],
) -> set[str]:
    return organization_permissions | project_permissions.get(str(project_id), set())


def project_permission_is_allowed(
    permission_key: str,
    *,
    project_id: UUID | str,
    organization_permissions: set[str],
    project_permissions: dict[str, set[str]],
) -> bool:
    return permission_key in effective_project_permissions(
        project_id=project_id,
        organization_permissions=organization_permissions,
        project_permissions=project_permissions,
    )
