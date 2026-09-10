from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.authorization.models import (
    MembershipRole,
    OrganizationAuthorizationState,
    Permission,
    Role,
    RolePermission,
)
from app.modules.configuration.models import OrganizationConfigurationState
from app.modules.events.service import enqueue_event
from app.modules.features.models import OrganizationFeature
from app.modules.features.registry import (
    FEATURE_REGISTRY,
    FEATURES_BY_KEY,
    FeatureReleaseState,
    FeatureSensitivity,
    FeatureSpec,
)
from app.modules.features.schemas import AccessContext, VisibleFeature
from app.modules.identity.models import MembershipStatus, OrganizationMembership
from app.modules.projects.access import load_project_permissions, visible_project_scope
from app.runtime.deployment import build_runtime_plan
from app.runtime.modules import MODULES_BY_KEY


def _release_is_visible(feature: FeatureSpec, allow_preview: bool) -> bool:
    if feature.release_state == FeatureReleaseState.AVAILABLE:
        return True
    return allow_preview and feature.release_state == FeatureReleaseState.PREVIEW


def _audit_risk(feature: FeatureSpec) -> AuditRisk:
    if feature.sensitivity == FeatureSensitivity.HIGH:
        return AuditRisk.HIGH
    if feature.sensitivity == FeatureSensitivity.SENSITIVE:
        return AuditRisk.MEDIUM
    return AuditRisk.LOW


def resolve_visible_features(
    permission_keys: set[str],
    overrides: Mapping[str, bool] | None = None,
    *,
    allow_preview: bool = False,
    deployment_modules: set[str] | frozenset[str] | None = None,
) -> list[FeatureSpec]:
    overrides = overrides or {}
    visibility: dict[str, bool] = {}

    def is_visible(feature: FeatureSpec) -> bool:
        cached = visibility.get(feature.key)
        if cached is not None:
            return cached

        if (
            deployment_modules is not None
            and feature.key in MODULES_BY_KEY
            and feature.key not in deployment_modules
        ):
            visibility[feature.key] = False
            return False

        if not _release_is_visible(feature, allow_preview):
            visibility[feature.key] = False
            return False

        if feature.required_permissions and not set(feature.required_permissions).issubset(
            permission_keys
        ):
            visibility[feature.key] = False
            return False

        enabled = feature.enabled_by_default
        if feature.tenant_configurable and feature.key in overrides:
            enabled = overrides[feature.key]
        if not enabled:
            visibility[feature.key] = False
            return False

        if feature.parent_key is not None:
            parent = FEATURES_BY_KEY[feature.parent_key]
            if not is_visible(parent):
                visibility[feature.key] = False
                return False

        visibility[feature.key] = True
        return True

    return sorted(
        (feature for feature in FEATURE_REGISTRY if is_visible(feature)),
        key=lambda feature: (feature.display_order, feature.key),
    )


async def build_access_context(db: AsyncSession, membership_id: UUID) -> AccessContext:
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise ValueError("Active organization membership was not found")

    permission_rows = await db.scalars(
        select(RolePermission.permission_key)
        .join(Role, Role.id == RolePermission.role_id)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .join(Permission, Permission.key == RolePermission.permission_key)
        .where(
            MembershipRole.membership_id == membership.id,
            Role.organization_id == membership.organization_id,
            Role.is_active.is_(True),
            Permission.is_active.is_(True),
        )
        .distinct()
        .order_by(RolePermission.permission_key)
    )
    organization_permissions = set(permission_rows.all())

    project_permissions = await load_project_permissions(
        db,
        organization_id=membership.organization_id,
        organization_membership_id=membership.id,
    )
    project_scope = visible_project_scope(organization_permissions, project_permissions)

    feature_permissions = set(organization_permissions)
    for project_id, scoped_permissions in project_permissions.items():
        if "*" in project_scope or project_id in project_scope:
            feature_permissions.update(scoped_permissions)

    feature_rows = await db.scalars(
        select(OrganizationFeature).where(
            OrganizationFeature.organization_id == membership.organization_id
        )
    )
    overrides = {row.feature_key: row.enabled for row in feature_rows.all()}

    authorization_revision = await db.scalar(
        select(OrganizationAuthorizationState.revision).where(
            OrganizationAuthorizationState.organization_id == membership.organization_id
        )
    )
    configuration_revision = await db.scalar(
        select(OrganizationConfigurationState.revision).where(
            OrganizationConfigurationState.organization_id == membership.organization_id
        )
    )

    runtime_plan = build_runtime_plan(get_settings())
    visible_features = resolve_visible_features(
        feature_permissions,
        overrides,
        deployment_modules=runtime_plan.module_keys,
    )

    return AccessContext(
        organization_id=membership.organization_id,
        membership_id=membership.id,
        authorization_revision=authorization_revision or 1,
        configuration_revision=configuration_revision or 1,
        permissions=sorted(organization_permissions),
        scopes={"project": sorted(project_scope)},
        project_permissions={
            project_id: sorted(permission_keys)
            for project_id, permission_keys in sorted(project_permissions.items())
        },
        features=[
            VisibleFeature(
                key=feature.key,
                name=feature.name,
                kind=feature.kind,
                parent_key=feature.parent_key,
                route=feature.route,
                sensitivity=feature.sensitivity,
                display_order=feature.display_order,
                mobile_enabled=feature.mobile_enabled,
                offline_enabled=feature.offline_enabled,
                help_topic=feature.help_topic,
            )
            for feature in visible_features
        ],
    )


async def set_feature_override(
    db: AsyncSession,
    organization_id: UUID,
    feature_key: str,
    enabled: bool,
    *,
    actor_user_id: UUID | None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
    configuration: dict[str, object] | None = None,
) -> OrganizationFeature:
    feature = FEATURES_BY_KEY.get(feature_key)
    if feature is None:
        raise ValueError("Unknown feature key")
    if not feature.tenant_configurable:
        raise ValueError("This feature cannot be configured by a tenant")
    if feature.release_state == FeatureReleaseState.RETIRED:
        raise ValueError("Retired features cannot be enabled")
    if enabled and feature_key in MODULES_BY_KEY:
        runtime_plan = build_runtime_plan(get_settings())
        if not runtime_plan.module_enabled(feature_key):
            raise ValueError("This feature is not available in the current deployment")

    row = await db.get(OrganizationFeature, (organization_id, feature_key))
    existing_configuration = dict(row.configuration) if row is not None else {}
    if configuration is not None and configuration != existing_configuration:
        raise ValueError(
            "Feature business configuration must use the registered configuration service"
        )

    previous = {
        "enabled": row.enabled if row is not None else feature.enabled_by_default,
        "version": row.version if row is not None else None,
    }

    if row is None:
        row = OrganizationFeature(
            organization_id=organization_id,
            feature_key=feature_key,
            enabled=enabled,
            configuration={},
            updated_by_user_id=actor_user_id,
        )
        db.add(row)
    else:
        row.enabled = enabled
        row.version += 1
        row.updated_by_user_id = actor_user_id

    auth_state = await db.get(OrganizationAuthorizationState, organization_id)
    if auth_state is None:
        auth_state = OrganizationAuthorizationState(organization_id=organization_id, revision=2)
        db.add(auth_state)
    else:
        auth_state.revision += 1

    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="feature.enablement.changed",
        target_type="feature",
        target_id=feature_key,
        actor_type=AuditActorType.USER if actor_user_id is not None else AuditActorType.SYSTEM,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=_audit_risk(feature),
        reason=reason,
        changes={
            "before": previous,
            "after": {
                "enabled": row.enabled,
                "version": row.version,
            },
        },
        metadata={
            "release_state": feature.release_state.value,
            "legacy_configuration_preserved": bool(existing_configuration),
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="access_context.changed",
        entity_type="organization",
        entity_id=organization_id,
        entity_version=auth_state.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"authorization_revision": auth_state.revision},
    )
    return row
