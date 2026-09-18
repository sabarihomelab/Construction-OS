from fastapi.routing import iter_route_contexts
from sqlalchemy import Numeric

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.equipment.api import router as equipment_router
from app.modules.equipment.consumption_models import MaterialConsumption
from app.modules.equipment.consumption_schemas import (
    MaterialConsumptionCreate,
    MaterialConsumptionPost,
)
from app.modules.financials.api import router as financial_router
from app.modules.financials.job_cost_models import ProjectCostSourceType
from app.modules.financials.material_feed_schemas import MaterialConsumptionCostPost
from app.runtime.modules import MODULES_BY_KEY


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables[table_name].foreign_key_constraints
    }


def test_material_consumption_table_is_registered_and_project_scoped() -> None:
    assert MaterialConsumption.__tablename__ in Base.metadata.tables
    targets = _fk_targets(MaterialConsumption.__tablename__)
    assert ("projects.id", "projects.organization_id") in targets
    assert ("materials.id", "materials.organization_id") in targets
    assert (
        "project_wbs_codes.id",
        "project_wbs_codes.project_id",
        "project_wbs_codes.organization_id",
    ) in targets
    assert (
        "project_boq_items.id",
        "project_boq_items.project_id",
        "project_boq_items.organization_id",
    ) in targets
    assert (
        "project_memberships.project_id",
        "project_memberships.organization_membership_id",
        "project_memberships.organization_id",
    ) in targets


def test_material_consumption_create_cannot_inject_authoritative_context() -> None:
    forbidden = {
        "organization_id",
        "project_id",
        "currency_code",
        "status",
        "total_cost",
        "posted_by_membership_id",
        "posted_at",
    }
    assert forbidden.isdisjoint(MaterialConsumptionCreate.model_fields)


def test_material_consumption_post_is_revision_protected_and_not_amount_driven() -> None:
    assert set(MaterialConsumptionPost.model_fields) == {
        "expected_revision",
        "unit_cost",
        "cost_basis",
        "reason",
    }
    assert "total_cost" not in MaterialConsumptionPost.model_fields


def test_material_financial_feed_only_selects_material_cost_head() -> None:
    assert set(MaterialConsumptionCostPost.model_fields) == {"material_cost_head_id"}


def test_material_consumption_and_financial_feed_routes_are_composed() -> None:
    assert MODULES_BY_KEY["equipment"].api_router == "app.modules.equipment.api:router"
    equipment_paths = {context.path for context in iter_route_contexts(equipment_router.routes)}
    assert "/projects/{project_id}/materials/consumptions" in equipment_paths
    assert (
        "/projects/{project_id}/materials/consumptions/{consumption_id}/post"
        in equipment_paths
    )

    financial_paths = {context.path for context in iter_route_contexts(financial_router.routes)}
    assert (
        "/projects/{project_id}/financials/job-cost/from-material-consumptions/{consumption_id}"
        in financial_paths
    )


def test_job_cost_supports_material_consumption_source() -> None:
    assert ProjectCostSourceType.MATERIAL_CONSUMPTION.value == "material_consumption"


def test_job_cost_allocation_preserves_four_decimal_quantities() -> None:
    column_type = Base.metadata.tables["project_cost_allocations"].c.quantity.type
    assert isinstance(column_type, Numeric)
    assert column_type.precision == 20
    assert column_type.scale == 4
