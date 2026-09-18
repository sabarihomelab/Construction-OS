from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.organizations.models import Organization, OrganizationSettings


class OrganizationValidationError(ValueError):
    pass


class OrganizationConflictError(ValueError):
    pass


async def get_company_profile(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> tuple[Organization, OrganizationSettings]:
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.is_active.is_(True),
        )
    )
    if organization is None:
        raise OrganizationValidationError("Company was not found")
    settings = await db.get(OrganizationSettings, organization_id)
    if settings is None:
        raise OrganizationValidationError("Company settings were not initialized")
    return organization, settings


async def update_company_profile(
    db: AsyncSession,
    *,
    organization_id: UUID,
    expected_updated_at: datetime,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> Organization:
    organization = await db.scalar(
        select(Organization)
        .where(Organization.id == organization_id, Organization.is_active.is_(True))
        .with_for_update()
    )
    if organization is None:
        raise OrganizationValidationError("Company was not found")
    if organization.updated_at != expected_updated_at:
        raise OrganizationConflictError("Company profile changed; refresh before saving")

    before = {"name": organization.name, "legal_name": organization.legal_name}
    if "name" in changes:
        name = str(changes["name"] or "").strip()
        if not name:
            raise OrganizationValidationError("Company name cannot be blank")
        organization.name = name
    if "legal_name" in changes:
        value = changes["legal_name"]
        organization.legal_name = str(value).strip() if value else None

    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="organization.profile.updated",
        target_type="organization",
        target_id=str(organization.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "before": before,
            "after": {"name": organization.name, "legal_name": organization.legal_name},
        },
    )
    return organization


async def update_company_settings(
    db: AsyncSession,
    *,
    organization_id: UUID,
    expected_settings_version: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> OrganizationSettings:
    settings = await db.scalar(
        select(OrganizationSettings)
        .where(OrganizationSettings.organization_id == organization_id)
        .with_for_update()
    )
    if settings is None:
        raise OrganizationValidationError("Company settings were not initialized")
    if settings.settings_version != expected_settings_version:
        raise OrganizationConflictError("Company settings changed; refresh before saving")

    mutable = {
        "locale",
        "timezone",
        "base_currency",
        "unit_system",
        "time_format",
        "first_day_of_week",
        "storage_quota_bytes",
    }
    before = {key: getattr(settings, key) for key in mutable}
    for key, value in changes.items():
        if key not in mutable:
            continue
        if key == "base_currency" and isinstance(value, str):
            value = value.strip().upper()
        if key in {"locale", "timezone"} and isinstance(value, str):
            value = value.strip()
        setattr(settings, key, value)

    settings.settings_version += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="organization.settings.updated",
        target_type="organization_settings",
        target_id=str(organization_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "before": before,
            "after": {
                **{key: getattr(settings, key) for key in mutable},
                "settings_version": settings.settings_version,
            },
        },
    )
    return settings
