from decimal import Decimal

import pytest
from pydantic import ValidationError
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
from app.modules.search.providers import search_projection_providers
from app.modules.workforce.management_router import router as management_router
from app.modules.workforce.models import ProjectWorkerRate
from app.modules.workforce.router import router as core_router
from app.modules.workforce.schemas import ProjectWorkerRateCreate, TimeEntryWrite, WorkerCreate
from app.modules.workforce.search import timecard_search_projection, worker_search_projection
from app.runtime.modules import MODULES_BY_KEY, resolve_runtime_modules


def _constraint_names(table_name: str) -> set[str | None]:
    return {constraint.name for constraint in Base.metadata.tables[table_name].constraints}


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def test_workforce_tables_replace_unsafe_scaffold() -> None:
    expected = {
        "workers",
        "crews",
        "crew_memberships",
        "project_worker_assignments",
        ProjectWorkerRate.__tablename__,
        "timecards",
        "workforce_time_entries",
        "timecard_history_events",
    }
    assert expected.issubset(Base.metadata.tables)
    assert "employees" not in Base.metadata.tables
    assert "time_entries" not in Base.metadata.tables


def test_worker_create_never_accepts_tenant_identity() -> None:
    assert "organization_id" not in WorkerCreate.model_fields


def test_worker_and_staffing_relationships_are_tenant_safe() -> None:
    assert (
        "organization_memberships.id",
        "organization_memberships.organization_id",
    ) in _fk_targets("workers")
    assert ("workers.id", "workers.organization_id") in _fk_targets("crews")
    assert ("projects.id", "projects.organization_id") in _fk_targets(
        "project_worker_assignments"
    )
    assert (
        "commercial_parties.id",
        "commercial_parties.organization_id",
    ) in _fk_targets("project_worker_assignments")
    assert (
        "project_worker_assignments.project_id",
        "project_worker_assignments.worker_id",
        "project_worker_assignments.organization_id",
    ) in _fk_targets("timecards")
    assert (
        "project_worker_assignments.id",
        "project_worker_assignments.project_id",
        "project_worker_assignments.organization_id",
    ) in _fk_targets("project_worker_rates")
    assert "uq_project_worker_assignments_project_worker_org" in _constraint_names(
        "project_worker_assignments"
    )
    assert "uq_project_worker_assignments_scope" in _constraint_names(
        "project_worker_assignments"
    )


def test_workforce_relationships_use_revisions_for_concurrent_admin_changes() -> None:
    assert "ck_workers_revision" in _constraint_names("workers")
    assert "ck_crews_revision" in _constraint_names("crews")
    assert "ck_crew_memberships_revision" in _constraint_names("crew_memberships")
    assert "ck_project_worker_assignments_revision" in _constraint_names(
        "project_worker_assignments"
    )
    assert "ck_project_worker_rates_revision" in _constraint_names("project_worker_rates")
    assert "ck_timecards_revision" in _constraint_names("timecards")


def test_project_worker_rates_are_decimal_effective_dated_and_nonnegative() -> None:
    table = Base.metadata.tables["project_worker_rates"]
    for column_name in ("regular_rate", "overtime_rate", "double_time_rate", "billing_rate"):
        assert isinstance(table.c[column_name].type, Numeric)
    assert "ck_project_worker_rates_date_range" in _constraint_names("project_worker_rates")
    assert "ck_project_worker_rates_regular_nonnegative" in _constraint_names(
        "project_worker_rates"
    )

    with pytest.raises(ValidationError):
        ProjectWorkerRateCreate(
            wage_basis="daily",
            regular_rate=Decimal("-1"),
            effective_from="2026-09-11",
        )


def test_time_hours_are_decimal_and_database_bounded() -> None:
    table = Base.metadata.tables["workforce_time_entries"]
    assert isinstance(table.c.regular_hours.type, Numeric)
    assert isinstance(table.c.overtime_hours.type, Numeric)
    assert isinstance(table.c.double_time_hours.type, Numeric)
    assert "ck_workforce_time_entries_daily_hours" in _constraint_names(
        "workforce_time_entries"
    )


def test_time_entry_schema_rejects_more_than_24_hours() -> None:
    with pytest.raises(ValidationError):
        TimeEntryWrite(
            work_date="2026-09-10",
            regular_hours=Decimal(16),
            overtime_hours=Decimal(9),
        )


def test_workforce_permissions_are_atomic() -> None:
    expected = {
        "workforce.worker.view",
        "workforce.worker.manage",
        "workforce.crew.view",
        "workforce.crew.manage",
        "workforce.assignment.view",
        "workforce.assignment.manage",
        "workforce.rate.view",
        "workforce.rate.manage",
        "workforce.timecard.view",
        "workforce.timecard.create",
        "workforce.timecard.update",
        "workforce.timecard.submit",
        "workforce.timecard.approve",
        "workforce.timecard.manage",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)


def test_workforce_feature_is_installer_selectable_but_hidden_until_ui_release() -> None:
    feature = FEATURES_BY_KEY["workforce"]
    assert feature.required_permissions == ("workforce.worker.view",)
    assert feature.release_state == FeatureReleaseState.PLANNED
    assert feature.offline_enabled

    manifest = MODULES_BY_KEY["workforce"]
    assert manifest.dependencies == ("projects",)
    assert {"field", "equipment", "safety"}.issubset(manifest.integrates_with)
    assert {item.key for item in resolve_runtime_modules("workforce")} == {
        "projects",
        "workforce",
    }


def test_workforce_configuration_uses_shared_hierarchy() -> None:
    week_start = CONFIGURATION_BY_KEY["workforce.timecards.week_start_day"]
    daily_hours = CONFIGURATION_BY_KEY["workforce.timecards.max_daily_hours"]
    approval = CONFIGURATION_BY_KEY["workforce.timecards.approval.required"]
    columns = CONFIGURATION_BY_KEY["workforce.timecards.visible_columns"]

    assert normalize_configuration_value(week_start, "friday") == "friday"
    with pytest.raises(ValueError):
        normalize_configuration_value(week_start, "noday")
    assert normalize_configuration_value(daily_hours, Decimal("12.50")) == "12.50"
    assert approval.change_class == ConfigurationChangeClass.WORKFLOW
    assert columns.mutability == ConfigurationMutability.USER_PREFERENCE
    assert columns.change_class == ConfigurationChangeClass.PRESENTATION


def test_workforce_search_providers_are_shared_registry_providers() -> None:
    assert search_projection_providers.get("worker") is worker_search_projection
    assert search_projection_providers.get("timecard") is timecard_search_projection


def test_workforce_router_contract_exposes_staffing_rates_and_timecard_lifecycle() -> None:
    paths = {
        route.path
        for source_router in (core_router, management_router)
        for route in source_router.routes
        if hasattr(route, "path")
    }
    assert "/workforce/workers" in paths
    assert "/workforce/crews/{crew_id}/memberships/{crew_membership_id}/end" in paths
    assert "/projects/{project_id}/workforce/assignments" in paths
    assert "/projects/{project_id}/workforce/assignments/{assignment_id}/rates" in paths
    assert (
        "/projects/{project_id}/workforce/assignments/{assignment_id}/rates/{rate_id}/end"
        in paths
    )
    assert "/projects/{project_id}/timecards/{timecard_id}/entries" in paths
    assert "/projects/{project_id}/timecards/{timecard_id}/submit" in paths
    assert "/projects/{project_id}/timecards/{timecard_id}/approve" in paths
    assert "/projects/{project_id}/timecards/{timecard_id}/reject" in paths
