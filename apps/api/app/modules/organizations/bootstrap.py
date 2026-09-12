import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
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
from app.modules.authorization.templates import INDIA_ROLE_TEMPLATES
from app.modules.identity.models import (
    MembershipKind,
    MembershipStatus,
    OrganizationMembership,
    User,
)
from app.modules.organizations.models import (
    INDIA_DEFAULT_CURRENCY,
    INDIA_DEFAULT_LOCALE,
    INDIA_DEFAULT_TIMEZONE,
    Organization,
    OrganizationSettings,
    TimeFormat,
    UnitSystem,
)


class CompanyBootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CompanyBootstrapResult:
    organization_id: str
    membership_id: str
    admin_user_id: str
    admin_email: str
    role_id: str


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or "@" not in normalized:
        raise CompanyBootstrapError("Administrator email is invalid")
    return normalized


def _normalize_slug(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
        raise CompanyBootstrapError(
            "Company slug must contain lowercase letters, numbers and single hyphens only"
        )
    if not 2 <= len(normalized) <= 100:
        raise CompanyBootstrapError("Company slug must be between 2 and 100 characters")
    return normalized


async def bootstrap_initial_company(
    db: AsyncSession,
    *,
    company_name: str,
    company_slug: str,
    admin_email: str,
    admin_display_name: str,
    legal_name: str | None = None,
) -> CompanyBootstrapResult:
    existing_organizations = await db.scalar(select(func.count()).select_from(Organization))
    if existing_organizations:
        raise CompanyBootstrapError(
            "Company bootstrap is first-run only; an organization already exists"
        )

    name = company_name.strip()
    display_name = admin_display_name.strip()
    if not name:
        raise CompanyBootstrapError("Company name is required")
    if not display_name:
        raise CompanyBootstrapError("Administrator display name is required")

    organization = Organization(
        name=name,
        legal_name=legal_name.strip() if legal_name and legal_name.strip() else None,
        slug=_normalize_slug(company_slug),
        country_code="IN",
        is_active=True,
    )
    db.add(organization)
    await db.flush()

    settings = OrganizationSettings(
        organization_id=organization.id,
        locale=INDIA_DEFAULT_LOCALE,
        timezone=INDIA_DEFAULT_TIMEZONE,
        base_currency=INDIA_DEFAULT_CURRENCY,
        unit_system=UnitSystem.METRIC,
        time_format=TimeFormat.TWENTY_FOUR_HOUR,
        first_day_of_week=1,
        settings_version=1,
    )
    db.add(settings)

    user = User(
        primary_email=_normalize_email(admin_email),
        display_name=display_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        kind=MembershipKind.INTERNAL,
        status=MembershipStatus.ACTIVE,
        joined_at=datetime.now(UTC),
    )
    db.add(membership)

    admin_role = Role(
        organization_id=organization.id,
        key="company-admin",
        name="Company Administrator",
        description="Protected first-run administrator role for this Construction OS company.",
        is_template=False,
        is_protected=True,
        is_active=True,
        version=1,
    )
    db.add(admin_role)
    await db.flush()

    permission_keys = list(
        (
            await db.scalars(
                select(Permission.key).where(Permission.is_active.is_(True)).order_by(Permission.key)
            )
        ).all()
    )
    if not permission_keys:
        raise CompanyBootstrapError("Permission catalog is empty; apply all migrations first")
    available_permissions = set(permission_keys)

    db.add_all(
        [RolePermission(role_id=admin_role.id, permission_key=key) for key in permission_keys]
    )
    db.add(MembershipRole(membership_id=membership.id, role_id=admin_role.id))

    seeded_role_keys: list[str] = []
    for template in INDIA_ROLE_TEMPLATES:
        role = Role(
            organization_id=organization.id,
            key=template.key,
            name=template.name,
            description=template.description,
            is_template=True,
            is_protected=False,
            is_active=True,
            version=1,
        )
        db.add(role)
        await db.flush()
        db.add_all(
            [
                RolePermission(role_id=role.id, permission_key=key)
                for key in sorted(template.permission_keys & available_permissions)
            ]
        )
        seeded_role_keys.append(role.key)

    db.add(OrganizationAuthorizationState(organization_id=organization.id, revision=1))
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization.id,
        action="organization.bootstrap.completed",
        target_type="organization",
        target_id=str(organization.id),
        actor_type=AuditActorType.USER,
        actor_user_id=user.id,
        risk=AuditRisk.CRITICAL,
        changes={
            "company": {
                "name": organization.name,
                "slug": organization.slug,
                "country_code": organization.country_code,
            },
            "admin": {
                "user_id": str(user.id),
                "membership_id": str(membership.id),
                "email": user.primary_email,
                "role_key": admin_role.key,
            },
            "default_roles": seeded_role_keys,
            "localization": {
                "locale": settings.locale,
                "timezone": settings.timezone,
                "base_currency": settings.base_currency,
                "unit_system": settings.unit_system.value,
            },
        },
    )

    return CompanyBootstrapResult(
        organization_id=str(organization.id),
        membership_id=str(membership.id),
        admin_user_id=str(user.id),
        admin_email=user.primary_email,
        role_id=str(admin_role.id),
    )
