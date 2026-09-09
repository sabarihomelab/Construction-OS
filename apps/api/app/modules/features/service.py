from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.models import (
    MembershipRole,
    OrganizationAuthorizationState,
    Permission,
    Role,
    RolePermission,
)
from app.modules.features.models import OrganizationFeature
from app.modules.features.registry import (
    FEATURES_BY_KEY,
    FEATURE_REGISTRY,
    FeatureReleaseState,
    FeatureSpec,
)
from app.modules.features.schemas import AccessContext, VisibleFeature
from app.modules.identity.models import MembershipStatus, OrganizationMembership


def _release_is_visible(feature: FeatureSpec, allow_preview: bool) -> bool:
    if feature.release_state == FeatureReleaseState.AVAILABLE:
        return True
    return allow_preview and feature.release_state == FeatureReleaseState.PREVIEW


def resolve_visible_features(
    permission_keys: set[str],
    overrides: Mapping[str, bool] | None = None,
    *,
    allow_preview: bool = False,
) -> list[FeatureSpec]:
    overrides = overrides or {}
    visibility: dict[str, bool] = {}

    def is_visible(feature: FeatureSpec) -> bool:
        cached = visibility.get(feature.key)
        if cached is not None:
            return cached

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
    permission_keys = set(permission_rows.all())

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

    visible_features = resolve_visible_features(permission_keys, overrides)

    return AccessContext(
        organization_id=membership.organization_id,
        membership_id=membership.id,
        authorization_revision=authorization_revision or 1,
        permissions=sorted(permission_keys),
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
    configuration: dict[str, object] | None = None,
) -> OrganizationFeature:
    feature = FEATURES_BY_KEY.get(feature_key)
    if feature is None:
        raise ValueError("Unknown feature key")
    if not feature.tenant_configurable:
        raise ValueError("This feature cannot be configured by a tenant")
    if feature.release_state == FeatureReleaseState.RETIRED:
        raise ValueError("Retired features cannot be enabled")

    row = await db.get(OrganizationFeature, (organization_id, feature_key))
    if row is None:
        row = OrganizationFeature(
            organization_id=organization_id,
            feature_key=feature_key,
            enabled=enabled,
            configuration=configuration or {},
            updated_by_user_id=actor_user_id,
        )
        db.add(row)
    else:
        row.enabled = enabled
        row.configuration = configuration or {}
        row.version += 1
        row.updated_by_user_id = actor_user_id

    auth_state = await db.get(OrganizationAuthorizationState, organization_id)
    if auth_state is None:
        auth_state = OrganizationAuthorizationState(organization_id=organization_id, revision=2)
        db.add(auth_state)
    else:
        auth_state.revision += 1

    await db.flush()
    return row
