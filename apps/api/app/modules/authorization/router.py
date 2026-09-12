from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.authorization.models import Role
from app.modules.authorization.schemas import (
    AssignedRoleRead,
    MembershipAdminCreate,
    MembershipAdminRead,
    MembershipRoleSet,
    MembershipStatusSet,
    PermissionDefinition,
    RoleClone,
    RoleCreateWithPermissions,
    RoleFromTemplate,
    RolePermissionSet,
    RoleRead,
    RoleTemplateRead,
    RoleUpdate,
)
from app.modules.authorization.service import (
    AuthorizationConflictError,
    AuthorizationValidationError,
    add_membership,
    clone_role,
    create_role,
    create_role_from_template,
    install_default_roles,
    list_memberships,
    list_permissions,
    list_roles,
    replace_membership_roles,
    replace_role_permissions,
    role_permission_keys,
    set_membership_status,
    update_role,
)
from app.modules.authorization.templates import INDIA_ROLE_TEMPLATES
from app.modules.features.service import build_access_context
from app.modules.identity.models import OrganizationMembership
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(prefix="/security", tags=["security"])


def _require_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, AuthorizationConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _membership_read(membership, user, roles: list[Role]) -> MembershipAdminRead:
    assigned = [
        AssignedRoleRead(
            id=role.id,
            key=role.key,
            name=role.name,
            is_template=role.is_template,
            is_protected=role.is_protected,
        )
        for role in roles
    ]
    return MembershipAdminRead(
        id=membership.id,
        user_id=user.id,
        primary_email=user.primary_email,
        display_name=user.display_name,
        kind=membership.kind,
        status=membership.status,
        role_ids=[role.id for role in roles],
        roles=assigned,
    )


@router.get("/permissions", response_model=list[PermissionDefinition])
async def get_permissions(db: DbSession, session: CurrentSession):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.view")
    return await list_permissions(db)


@router.get("/role-templates", response_model=list[RoleTemplateRead])
async def get_role_templates(db: DbSession, session: CurrentSession) -> list[RoleTemplateRead]:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.view")
    return [
        RoleTemplateRead(
            key=template.key,
            name=template.name,
            description=template.description,
            scope_hint=template.scope_hint,
            membership_kind_hint=template.membership_kind_hint,
            permission_keys=sorted(template.permission_keys),
        )
        for template in INDIA_ROLE_TEMPLATES
    ]


@router.get("/roles", response_model=list[RoleRead])
async def get_roles(db: DbSession, session: CurrentSession):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.view")
    return await list_roles(db, context.organization_id)


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def post_role(
    payload: RoleCreateWithPermissions,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        role = await create_role(
            db,
            organization_id=context.organization_id,
            key=payload.key,
            name=payload.name,
            description=payload.description,
            permission_keys=set(payload.permission_keys),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(role)
        return role
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/roles/install-defaults", response_model=list[RoleRead])
async def post_default_roles(
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        roles = await install_default_roles(
            db,
            organization_id=context.organization_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        return roles
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/roles/from-template/{template_key}",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_role_from_template(
    template_key: str,
    payload: RoleFromTemplate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        role = await create_role_from_template(
            db,
            organization_id=context.organization_id,
            template_key=template_key,
            key=payload.key,
            name=payload.name,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(role)
        return role
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/roles/{role_id}/clone",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_role_clone(
    role_id: UUID,
    payload: RoleClone,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        role = await clone_role(
            db,
            organization_id=context.organization_id,
            source_role_id=role_id,
            key=payload.key,
            name=payload.name,
            description=payload.description,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(role)
        return role
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/roles/{role_id}", response_model=RoleRead)
async def patch_role(
    role_id: UUID,
    payload: RoleUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        role = await update_role(
            db,
            organization_id=context.organization_id,
            role_id=role_id,
            expected_version=payload.expected_version,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(role)
        return role
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/roles/{role_id}/permissions", response_model=RolePermissionSet)
async def get_role_permissions(
    role_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> RolePermissionSet:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.view")
    role = await db.scalar(
        select(Role).where(Role.id == role_id, Role.organization_id == context.organization_id)
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RolePermissionSet(
        expected_version=role.version,
        permission_keys=await role_permission_keys(db, role.id),
    )


@router.put("/roles/{role_id}/permissions", response_model=RoleRead)
async def put_role_permissions(
    role_id: UUID,
    payload: RolePermissionSet,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    role = await db.scalar(
        select(Role).where(Role.id == role_id, Role.organization_id == context.organization_id)
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    try:
        role = await replace_role_permissions(
            db,
            organization_id=context.organization_id,
            role=role,
            permission_keys=set(payload.permission_keys),
            actor_user_id=session.user_id,
            session_id=session.id,
            expected_version=payload.expected_version,
        )
        await db.commit()
        await db.refresh(role)
        return role
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/memberships", response_model=list[MembershipAdminRead])
async def get_memberships(db: DbSession, session: CurrentSession) -> list[MembershipAdminRead]:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.view")
    rows = await list_memberships(db, context.organization_id)
    return [_membership_read(membership, user, roles) for membership, user, roles in rows]


@router.post(
    "/memberships",
    response_model=MembershipAdminRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_membership(
    payload: MembershipAdminCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MembershipAdminRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        membership = await add_membership(
            db,
            organization_id=context.organization_id,
            email=str(payload.primary_email),
            display_name=payload.display_name,
            kind=payload.kind,
            status=payload.status,
            role_ids=set(payload.role_ids),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        rows = await list_memberships(db, context.organization_id)
        for row_membership, user, roles in rows:
            if row_membership.id == membership.id:
                return _membership_read(row_membership, user, roles)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Membership readback failed")
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.put("/memberships/{membership_id}/roles", response_model=MembershipAdminRead)
async def put_membership_roles(
    membership_id: UUID,
    payload: MembershipRoleSet,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MembershipAdminRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == context.organization_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    try:
        await replace_membership_roles(
            db,
            organization_id=context.organization_id,
            membership=membership,
            role_ids=set(payload.role_ids),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        rows = await list_memberships(db, context.organization_id)
        for row_membership, user, roles in rows:
            if row_membership.id == membership.id:
                return _membership_read(row_membership, user, roles)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Membership readback failed")
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/memberships/{membership_id}/status", response_model=MembershipAdminRead)
async def patch_membership_status(
    membership_id: UUID,
    payload: MembershipStatusSet,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MembershipAdminRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "security.role.manage")
    try:
        membership = await set_membership_status(
            db,
            organization_id=context.organization_id,
            membership_id=membership_id,
            status=payload.status,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        rows = await list_memberships(db, context.organization_id)
        for row_membership, user, roles in rows:
            if row_membership.id == membership.id:
                return _membership_read(row_membership, user, roles)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Membership readback failed")
    except (AuthorizationConflictError, AuthorizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
