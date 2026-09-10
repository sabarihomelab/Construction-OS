from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.main import app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.configuration.models import (
    ConfigurationChangeClass,
    ConfigurationScopeType,
)
from app.modules.configuration.registry import (
    CONFIGURATION_BY_KEY,
    CONFIGURATION_DEFINITIONS,
    ConfigurationDefinition,
    ConfigurationMutability,
    ConfigurationValueType,
    normalize_configuration_value,
)
from app.modules.configuration.schemas import ConfigurationOverrideWrite
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.features.schemas import AccessContext


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def test_configuration_tables_are_registered() -> None:
    expected = {
        "organization_configuration_states",
        "configuration_values",
        "configuration_value_versions",
        "configuration_scope_revisions",
        "membership_preference_states",
        "membership_preferences",
    }
    assert expected.issubset(Base.metadata.tables)


def test_configuration_admin_capabilities_are_registered() -> None:
    assert {
        "admin.configuration.view",
        "admin.configuration.manage",
    }.issubset(PERMISSIONS_BY_KEY)


def test_configuration_admin_page_stays_hidden_until_ui_is_complete() -> None:
    feature = FEATURES_BY_KEY["admin.configuration"]
    assert feature.release_state == FeatureReleaseState.PLANNED
    assert feature.required_permissions == ("admin.configuration.view",)


def test_protected_definitions_cannot_declare_tenant_override_scopes() -> None:
    protected = [
        definition
        for definition in CONFIGURATION_DEFINITIONS
        if definition.mutability == ConfigurationMutability.PROTECTED
    ]
    assert protected
    assert all(not definition.allowed_scopes for definition in protected)


def test_user_preferences_are_presentation_only() -> None:
    preferences = [
        definition
        for definition in CONFIGURATION_DEFINITIONS
        if definition.mutability == ConfigurationMutability.USER_PREFERENCE
    ]
    assert preferences
    assert all(
        definition.change_class == ConfigurationChangeClass.PRESENTATION
        for definition in preferences
    )


def test_rfi_configuration_probe_supports_full_business_hierarchy() -> None:
    definition = CONFIGURATION_BY_KEY["rfis.default_due_days"]
    assert definition.allowed_scopes == (
        ConfigurationScopeType.COMPANY,
        ConfigurationScopeType.PROJECT_TEMPLATE,
        ConfigurationScopeType.PROJECT,
    )
    assert normalize_configuration_value(definition, 14) == 14
    with pytest.raises(ValueError):
        normalize_configuration_value(definition, -1)


def test_decimal_configuration_normalization_is_deterministic_when_used() -> None:
    definition = ConfigurationDefinition(
        key="test.rate",
        module_key="test",
        value_type=ConfigurationValueType.DECIMAL,
        default="0",
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=(ConfigurationScopeType.COMPANY,),
    )
    assert normalize_configuration_value(definition, Decimal("1.2300")) == "1.2300"


def test_override_schema_preserves_inherit_semantics() -> None:
    inherited = ConfigurationOverrideWrite(inherit=True)
    assert inherited.inherit
    assert inherited.value is None

    with pytest.raises(ValidationError):
        ConfigurationOverrideWrite(inherit=True, value=True)
    with pytest.raises(ValidationError):
        ConfigurationOverrideWrite(inherit=False)


def test_override_effective_time_requires_timezone() -> None:
    naive = datetime.fromisoformat("2026-09-10T12:00:00")
    with pytest.raises(ValidationError):
        ConfigurationOverrideWrite(value=1, effective_from=naive)


def test_project_template_reference_is_tenant_consistent() -> None:
    targets = _fk_targets("projects")
    assert (
        "configuration_template_versions.id",
        "configuration_template_versions.organization_id",
    ) in targets


def test_membership_preferences_are_tenant_and_project_safe() -> None:
    targets = _fk_targets("membership_preferences")
    assert (
        "organization_memberships.id",
        "organization_memberships.organization_id",
    ) in targets
    assert ("projects.id", "projects.organization_id") in targets


def test_access_context_keeps_configuration_revision_backward_compatible() -> None:
    assert AccessContext.model_fields["configuration_revision"].default == 1


def test_configuration_router_is_mounted_under_versioned_api() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/configuration/modules/{module_key}" in paths
    assert "/api/v1/configuration/projects/{project_id}/modules/{module_key}" in paths
    assert "/api/v1/configuration/preferences/{module_key}/{preference_key:path}" in paths
