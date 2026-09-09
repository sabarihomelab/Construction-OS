from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.features.registry import FEATURE_REGISTRY, FeatureReleaseState
from app.modules.features.service import resolve_visible_features


def test_organization_feature_table_is_registered() -> None:
    assert "organization_features" in Base.metadata.tables


def test_every_feature_permission_exists_in_permission_catalog() -> None:
    referenced_permissions = {
        permission
        for feature in FEATURE_REGISTRY
        for permission in feature.required_permissions
    }
    assert referenced_permissions.issubset(PERMISSIONS_BY_KEY)


def test_planned_feature_never_becomes_visible_from_tenant_override() -> None:
    permissions = {"projects.project.view"}
    features = resolve_visible_features(permissions, {"projects": True})
    assert "projects" not in {feature.key for feature in features}


def test_available_feature_requires_permission() -> None:
    features = resolve_visible_features(set())
    keys = {feature.key for feature in features}
    assert "home" in keys
    assert "help" not in keys
    assert "admin.operations" not in keys


def test_non_configurable_home_ignores_tenant_disable_override() -> None:
    features = resolve_visible_features(set(), {"home": False})
    assert "home" in {feature.key for feature in features}


def test_non_configurable_admin_ignores_tenant_disable_override() -> None:
    permissions = {"admin.settings.view", "admin.operations.view"}
    features = resolve_visible_features(permissions, {"admin": False})
    keys = {feature.key for feature in features}
    assert "admin" in keys
    assert "admin.operations" in keys


def test_only_available_features_are_shown_by_default() -> None:
    permissions = set(PERMISSIONS_BY_KEY)
    visible = resolve_visible_features(permissions)
    assert all(feature.release_state == FeatureReleaseState.AVAILABLE for feature in visible)
