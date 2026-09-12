from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.authorization.models import (
    MembershipRole,
    OrganizationAuthorizationState,
    Permission,
    Role,
    RolePermission,
)
from app.modules.authorization.templates import INDIA_ROLE_TEMPLATES, ROLE_TEMPLATES_BY_KEY
from app.modules.events.service import enqueue_event
from app.modules.identity.models import (
    MembershipKind,
    MembershipStatus,
    OrganizationMembership,
    User,
    UserStatus,
)


class AuthorizationValidationError(ValueError):
    pass


class AuthorizationConflictError(ValueError):
    pass


async def _touch_authorization(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID | None,
    session_id: UUID | None,
) -> int:
    state = await db.get(OrganizationAuthorizationState, organization_id)
    if state is None:
        state = OrganizationAuthorizationState(organization_id=organization_id, revision=1)
        db.add(state)
    else:
        state.revision += 1
    await db.flush()
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="access_context.changed",
        entity_type="organization",
        entity_id=organization_id,
        entity_version=state.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"authorization_revision": state.revision},
    )
    return state.revision


async def list_permissions(db: AsyncSession) -> list[Permission]:
    rows = await db.scalars(
        select(Permission).where(Permission.is_active.is_(True)).order_by(
            Permission.module, Permission.resource, Permission.action, Permission.key
        )
    )
    return list(rows.all())


async def list_roles(db: AsyncSession, organization_id: UUID) -> list[Role]:
    rows = await db.scalars(
        select(Role).where(Role.organization_id == organization_id).order_by(Role.name, Role.key)
    )
    return list(rows.all())


async def role_permission_keys(db: AsyncSession, role_id: UUID) -> set[str]:
    rows = await db.scalars(
        select(RolePermission.permission_key)
        .where(RolePermission.role_id == role_id)
        .order_by(RolePermission.permission_key)
    )
    return set(rows.all())


async def _load_role(db: AsyncSession, organization_id: UUID, role_id: UUID) -> Role:
    role = await db.scalar(
        select(Role).where(Role.id == role_id, Role.organization_id == organization_id)
    )
    if role is None:
        raise AuthorizationValidationError("Role was not found")
    return role


async def create_role(
    db: AsyncSession,
    *,
    organization_id: UUID,
    key: str,
    name: str,
    description: str | None,
    permission_keys: set[str] | None,
    actor_user_id: UUID,
    session_id: UUID | None,
    is_template: bool = False,
) -> Role:
    existing = await db.scalar(
        select(Role.id).where(Role.organization_id == organization_id, Role.key == key)
    )
    if existing is not None:
        raise AuthorizationConflictError("A role with this key already exists")

    role = Role(
        organization_id=organization_id,
        key=key,
        name=name.strip(),
        description=description.strip() if description and description.strip() else None,
        is_template=is_template,
        is_protected=False,
        is_active=True,
        version=1,
    )
    db.add(role)
    await db.flush()
    if permission_keys:
        await replace_role_permissions(
            db,
            organization_id=organization_id,
            role=role,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            session_id=session_id,
            audit=False,
        )
    else:
        await _touch_authorization(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="security.role.created",
        target_type="role",
        target_id=str(role.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={"key": role.key, "name": role.name, "is_template": role.is_template},
    )
    return role


async def update_role(
    db: AsyncSession,
    *,
    organization_id: UUID,
    role_id: UUID,
    expected_version: int,
    name: str | None,
    description: str | None,
    is_active: bool | None,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> Role:
    role = await _load_role(db, organization_id, role_id)
    if role.version != expected_version:
        raise AuthorizationConflictError("Role changed; refresh before saving")
    if role.is_protected:
        raise AuthorizationValidationError("Protected roles cannot be edited")
    before = {
        "name": role.name,
        "description": role.description,
        "is_active": role.is_active,
        "version": role.version,
    }
    if name is not None:
        role.name = name.strip()
    if description is not None:
        role.description = description.strip() or None
    if is_active is not None:
        role.is_active = is_active
    role.version += 1
    await _touch_authorization(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="security.role.updated",
        target_type="role",
        target_id=str(role.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "before": before,
            "after": {
                "name": role.name,
                "description": role.description,
                "is_active": role.is_active,
                "version": role.version,
            },
        },
    )
    return role


async def replace_role_permissions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    role: Role,
    permission_keys: set[str],
    actor_user_id: UUID,
    session_id: UUID | None,
    expected_version: int | None = None,
    audit: bool = True,
) -> Role:
    if role.organization_id != organization_id:
        raise AuthorizationValidationError("Role was not found")
    if role.is_protected:
        raise AuthorizationValidationError("Protected role permissions cannot be changed")
    if expected_version is not None and role.version != expected_version:
        raise AuthorizationConflictError("Role changed; refresh before saving")

    active_rows = await db.scalars(
        select(Permission.key).where(
            Permission.key.in_(permission_keys), Permission.is_active.is_(True)
        )
    ) if permission_keys else None
    valid_keys = set(active_rows.all()) if active_rows is not None else set()
    unknown = permission_keys - valid_keys
    if unknown:
        raise AuthorizationValidationError(
            "Unknown or inactive permission keys: " + ", ".join(sorted(unknown))
        )

    before = await role_permission_keys(db, role.id)
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
    db.add_all(
        [RolePermission(role_id=role.id, permission_key=key) for key in sorted(valid_keys)]
    )
    role.version += 1
    await _touch_authorization(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    if audit:
        await record_audit_event(
            db,
            organization_id=organization_id,
            action="security.role.permissions.changed",
            target_type="role",
            target_id=str(role.id),
            actor_type=AuditActorType.USER,
            actor_user_id=actor_user_id,
            session_id=session_id,
            risk=AuditRisk.CRITICAL,
            changes={
                "before": sorted(before),
                "after": sorted(valid_keys),
                "version": role.version,
            },
        )
    return role


async def clone_role(
    db: AsyncSession,
    *,
    organization_id: UUID,
    source_role_id: UUID,
    key: str,
    name: str,
    description: str | None,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> Role:
    source = await _load_role(db, organization_id, source_role_id)
    permissions = await role_permission_keys(db, source.id)
    return await create_role(
        db,
        organization_id=organization_id,
        key=key,
        name=name,
        description=description or source.description,
        permission_keys=permissions,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def create_role_from_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    template_key: str,
    key: str | None,
    name: str | None,
    actor_user_id: UUID,
    session_id: UUID | None,
    mark_default: bool = False,
) -> Role:
    template = ROLE_TEMPLATES_BY_KEY.get(template_key)
    if template is None:
        raise AuthorizationValidationError("Unknown role template")
    return await create_role(
        db,
        organization_id=organization_id,
        key=key or template.key,
        name=name or template.name,
        description=template.description,
        permission_keys=set(template.permission_keys),
        actor_user_id=actor_user_id,
        session_id=session_id,
        is_template=mark_default,
    )


async def install_default_roles(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> list[Role]:
    existing_rows = await db.scalars(
        select(Role).where(Role.organization_id == organization_id)
    )
    existing_by_key = {role.key: role for role in existing_rows.all()}
    installed: list[Role] = []
    for template in INDIA_ROLE_TEMPLATES:
        if template.key in existing_by_key:
            continue
        installed.append(
            await create_role_from_template(
                db,
                organization_id=organization_id,
                template_key=template.key,
                key=None,
                name=None,
                actor_user_id=actor_user_id,
                session_id=session_id,
                mark_default=True,
            )
        )
    return installed


async def list_memberships(
    db: AsyncSession, organization_id: UUID
) -> list[tuple[OrganizationMembership, User, list[Role]]]:
    memberships = list(
        (
            await db.scalars(
                select(OrganizationMembership)
                .where(OrganizationMembership.organization_id == organization_id)
                .order_by(OrganizationMembership.created_at, OrganizationMembership.id)
            )
        ).all()
    )
    result: list[tuple[OrganizationMembership, User, list[Role]]] = []
    for membership in memberships:
        user = await db.get(User, membership.user_id)
        if user is None:
            continue
        roles = list(
            (
                await db.scalars(
                    select(Role)
                    .join(MembershipRole, MembershipRole.role_id == Role.id)
                    .where(
                        MembershipRole.membership_id == membership.id,
                        Role.organization_id == organization_id,
                    )
                    .order_by(Role.name, Role.key)
                )
            ).all()
        )
        result.append((membership, user, roles))
    return result


async def add_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    email: str,
    display_name: str,
    kind: MembershipKind,
    status: MembershipStatus,
    role_ids: set[UUID],
    actor_user_id: UUID,
    session_id: UUID | None,
) -> OrganizationMembership:
    normalized_email = email.strip().lower()
    user = await db.scalar(select(User).where(func.lower(User.primary_email) == normalized_email))
    if user is None:
        user = User(
            primary_email=normalized_email,
            display_name=display_name.strip(),
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(user)
        await db.flush()
    elif display_name.strip() and user.display_name != display_name.strip():
        user.display_name = display_name.strip()

    existing = await db.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if existing is not None:
        raise AuthorizationConflictError("This person already belongs to the company")

    now = datetime.now(UTC)
    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=user.id,
        kind=kind,
        status=status,
        joined_at=now if status == MembershipStatus.ACTIVE else None,
        ended_at=now if status == MembershipStatus.ENDED else None,
    )
    db.add(membership)
    await db.flush()
    await replace_membership_roles(
        db,
        organization_id=organization_id,
        membership=membership,
        role_ids=role_ids,
        actor_user_id=actor_user_id,
        session_id=session_id,
        audit=False,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="security.membership.created",
        target_type="organization_membership",
        target_id=str(membership.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "email": normalized_email,
            "kind": membership.kind.value,
            "status": membership.status.value,
            "role_ids": [str(role_id) for role_id in sorted(role_ids, key=str)],
        },
    )
    return membership


async def replace_membership_roles(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership: OrganizationMembership,
    role_ids: set[UUID],
    actor_user_id: UUID,
    session_id: UUID | None,
    audit: bool = True,
) -> None:
    if membership.organization_id != organization_id:
        raise AuthorizationValidationError("Membership was not found")
    if role_ids:
        roles = list(
            (
                await db.scalars(
                    select(Role).where(
                        Role.id.in_(role_ids),
                        Role.organization_id == organization_id,
                        Role.is_active.is_(True),
                    )
                )
            ).all()
        )
        valid_ids = {role.id for role in roles}
        if valid_ids != role_ids:
            raise AuthorizationValidationError("One or more roles are unavailable")
    before = set(
        (
            await db.scalars(
                select(MembershipRole.role_id).where(MembershipRole.membership_id == membership.id)
            )
        ).all()
    )
    await db.execute(delete(MembershipRole).where(MembershipRole.membership_id == membership.id))
    db.add_all(
        [MembershipRole(membership_id=membership.id, role_id=role_id) for role_id in sorted(role_ids, key=str)]
    )
    await _touch_authorization(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    if audit:
        await record_audit_event(
            db,
            organization_id=organization_id,
            action="security.membership.roles.changed",
            target_type="organization_membership",
            target_id=str(membership.id),
            actor_type=AuditActorType.USER,
            actor_user_id=actor_user_id,
            session_id=session_id,
            risk=AuditRisk.CRITICAL,
            changes={
                "before": [str(value) for value in sorted(before, key=str)],
                "after": [str(value) for value in sorted(role_ids, key=str)],
            },
        )


async def set_membership_status(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    status: MembershipStatus,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> OrganizationMembership:
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise AuthorizationValidationError("Membership was not found")
    if membership.user_id == actor_user_id and status != MembershipStatus.ACTIVE:
        raise AuthorizationValidationError("You cannot suspend or end your own company membership")
    before = membership.status
    membership.status = status
    now = datetime.now(UTC)
    if status == MembershipStatus.ACTIVE and membership.joined_at is None:
        membership.joined_at = now
        membership.ended_at = None
    elif status == MembershipStatus.ENDED:
        membership.ended_at = now
    await _touch_authorization(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="security.membership.status.changed",
        target_type="organization_membership",
        target_id=str(membership.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={"before": before.value, "after": status.value},
    )
    return membership
