from decimal import Decimal

import pytest
from fastapi.routing import iter_route_contexts

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.equipment.api import router as equipment_router
from app.modules.equipment.usage_models import (
    EquipmentRateBasis,
    EquipmentUsage,
    ProjectEquipmentRate,
)
from app.modules.equipment.usage_schemas import EquipmentUsageCreate, EquipmentUsagePost
from app.modules.financials.api import router as financial_router
from app.modules.financials.equipment_cost_feeds import _usage_cost
from app.modules.financials.equipment_feed_schemas import EquipmentUsageCostPost
from app.modules.financials.job_cost_models import ProjectCostSourceType
from app.modules.financials.service import FinancialValidationError
from app.runtime.modules import MODULES_BY_KEY


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables[table_name].foreign_key_constraints
    }


def test_equipment_usage_and_rates_are_project_scoped_to_assignment() -> None:
    assignment_scope = (
        "project_equipment_assignments.id",
        "project_equipment_assignments.project_id",
        "project_equipment_assignments.organization_id",
    )
    assert assignment_scope in _fk_targets("equipment_usages")
    assert assignment_scope in _fk_targets("project_equipment_rates")

    assignment_table = Base.metadata.tables["project_equipment_assignments"]
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in assignment_table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("id", "project_id", "organization_id") in unique_column_sets


def test_equipment_usage_create_cannot_inject_financial_values() -> None:
    forbidden = {
        "organization_id",
        "project_id",
        "currency_code",
        "rate",
        "rate_basis",
        "amount",
        "total_cost",
        "status",
        "posted_by_membership_id",
        "posted_at",
    }
    assert forbidden.isdisjoint(EquipmentUsageCreate.model_fields)
    assert set(EquipmentUsagePost.model_fields) == {"expected_revision", "reason"}


def test_equipment_financial_feed_only_selects_equipment_cost_head() -> None:
    assert set(EquipmentUsageCostPost.model_fields) == {"equipment_cost_head_id"}
    assert EquipmentUsageCostPost.model_config.get("extra") == "forbid"


def test_equipment_usage_and_financial_feed_routes_are_composed() -> None:
    assert MODULES_BY_KEY["equipment"].api_router == "app.modules.equipment.api:router"
    equipment_paths = {context.path for context in iter_route_contexts(equipment_router.routes)}
    assert "/projects/{project_id}/equipment/usages" in equipment_paths
    assert "/projects/{project_id}/equipment/usages/{usage_id}/post" in equipment_paths
    assert (
        "/projects/{project_id}/equipment/assignments/{assignment_id}/rates"
        in equipment_paths
    )

    financial_paths = {context.path for context in iter_route_contexts(financial_router.routes)}
    assert (
        "/projects/{project_id}/financials/job-cost/from-equipment-usages/{usage_id}"
        in financial_paths
    )


def test_job_cost_supports_equipment_usage_source() -> None:
    assert ProjectCostSourceType.EQUIPMENT_USAGE.value == "equipment_usage"


def test_hourly_equipment_cost_uses_observed_hours_and_rate() -> None:
    usage = EquipmentUsage(operating_hours=Decimal("7.5000"))
    rate = ProjectEquipmentRate(rate_basis=EquipmentRateBasis.HOURLY, rate=Decimal("2000.0000"))
    assert _usage_cost(usage, rate) == Decimal("15000.00")


def test_non_hourly_equipment_rate_is_not_silently_converted() -> None:
    usage = EquipmentUsage(operating_hours=Decimal("7.5000"))
    rate = ProjectEquipmentRate(rate_basis=EquipmentRateBasis.DAILY, rate=Decimal("12000.0000"))
    with pytest.raises(FinancialValidationError, match="hourly equipment rates only"):
        _usage_cost(usage, rate)
