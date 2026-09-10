import pytest
from sqlalchemy import Numeric

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.configuration.models import ConfigurationChangeClass
from app.modules.configuration.registry import (
    CONFIGURATION_BY_KEY,
    ConfigurationMutability,
    normalize_configuration_value,
)
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.field.router import router as field_router
from app.modules.field.search import daily_report_search_projection
from app.modules.search.providers import search_projection_providers


def _constraint_names(table_name: str) -> set[str | None]:
    return {constraint.name for constraint in Base.metadata.tables[table_name].constraints}


def test_daily_report_tables_are_registered_without_legacy_scaffold_tables() -> None:
    expected = {
        "daily_reports",
        "daily_report_crew_entries",
        "daily_report_work_entries",
        "daily_report_equipment_entries",
        "daily_report_delivery_entries",
        "daily_report_production_entries",
        "daily_report_delay_entries",
        "daily_report_safety_entries",
        "daily_report_history_events",
    }
    assert expected.issubset(Base.metadata.tables)
    assert "daily_logs" not in Base.metadata.tables
    assert "time_entries" not in Base.metadata.tables


def test_daily_report_is_tenant_project_and_preparer_safe() -> None:
    constraints = _constraint_names("daily_reports")
    assert "fk_daily_reports_project_org" in constraints
    assert "fk_daily_reports_preparer_project_member_org" in constraints
    assert "fk_daily_reports_workflow_org" in constraints
    assert "uq_daily_reports_project_date_shift" in constraints


def test_daily_report_numeric_business_values_are_decimal_columns() -> None:
    checks = (
        ("daily_reports", "temperature_low"),
        ("daily_report_crew_entries", "regular_hours"),
        ("daily_report_work_entries", "quantity"),
        ("daily_report_equipment_entries", "hours_operated"),
        ("daily_report_delivery_entries", "quantity"),
        ("daily_report_production_entries", "quantity"),
        ("daily_report_delay_entries", "lost_hours"),
    )
    for table_name, column_name in checks:
        assert isinstance(Base.metadata.tables[table_name].c[column_name].type, Numeric)


def test_daily_report_permissions_are_atomic() -> None:
    expected = {
        "field.daily_report.view",
        "field.daily_report.create",
        "field.daily_report.update",
        "field.daily_report.submit",
        "field.daily_report.approve",
        "field.daily_report.manage",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)
    assert "field.daily_log.view" not in PERMISSIONS_BY_KEY


def test_field_feature_uses_new_permission_and_stays_hidden_until_ui_is_ready() -> None:
    feature = FEATURES_BY_KEY["field"]
    assert feature.required_permissions == ("field.daily_report.view",)
    assert feature.release_state == FeatureReleaseState.PLANNED
    assert feature.offline_enabled


def test_daily_report_sections_have_simple_contractor_defaults() -> None:
    enabled = CONFIGURATION_BY_KEY["field.daily_reports.sections.enabled"]
    required = CONFIGURATION_BY_KEY["field.daily_reports.sections.required"]
    assert enabled.default == ["crew", "work", "photos", "notes"]
    assert required.default == ["work"]


def test_daily_report_section_configuration_rejects_unknown_section() -> None:
    definition = CONFIGURATION_BY_KEY["field.daily_reports.sections.enabled"]
    assert normalize_configuration_value(definition, ["crew", "work"]) == ["crew", "work"]
    with pytest.raises(ValueError, match="unsupported"):
        normalize_configuration_value(definition, ["crew", "mystery_section"])


def test_daily_report_personal_preferences_cannot_change_business_rules() -> None:
    compact = CONFIGURATION_BY_KEY["field.daily_reports.compact_entry"]
    columns = CONFIGURATION_BY_KEY["field.daily_reports.visible_columns"]
    assert compact.mutability == ConfigurationMutability.USER_PREFERENCE
    assert columns.mutability == ConfigurationMutability.USER_PREFERENCE
    assert compact.change_class == ConfigurationChangeClass.PRESENTATION
    assert columns.change_class == ConfigurationChangeClass.PRESENTATION


def test_daily_report_workflow_configuration_reuses_shared_engine_identity() -> None:
    definition = CONFIGURATION_BY_KEY["field.daily_reports.workflow.definition_key"]
    assert definition.change_class == ConfigurationChangeClass.WORKFLOW
    assert definition.mutability == ConfigurationMutability.BUSINESS


def test_daily_report_search_provider_is_registered() -> None:
    assert search_projection_providers.get("daily_report") is daily_report_search_projection


def test_daily_report_router_defines_project_api_contract() -> None:
    paths = {f"/api/v1{route.path}" for route in field_router.routes}
    assert "/api/v1/projects/{project_id}/daily-reports" in paths
    assert "/api/v1/projects/{project_id}/daily-reports/{report_id}/sections" in paths
    assert "/api/v1/projects/{project_id}/daily-reports/{report_id}/submit" in paths
    assert "/api/v1/projects/{project_id}/daily-reports/{report_id}/history" in paths
