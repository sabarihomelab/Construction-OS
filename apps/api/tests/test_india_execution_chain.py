from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.estimating.models import ProjectBudget, ProjectEstimate
from app.modules.estimating.router import router as estimating_router
from app.modules.estimating.schemas import EstimateCreate
from app.modules.features.registry import FEATURES_BY_KEY
from app.modules.procurement.models import GoodsReceipt, PurchaseOrder, PurchaseRequisition
from app.modules.procurement.router import router as procurement_router
from app.modules.procurement.schemas import RequisitionCreate
from app.modules.scheduling.models import ProjectSchedule, ScheduleActivity, ScheduleBaseline
from app.modules.scheduling.router import router as scheduling_router
from app.modules.scheduling.schemas import ScheduleCreate
from app.modules.search.bootstrap import register_builtin_search_providers
from app.modules.search.providers import search_projection_providers
from app.modules.subcontracts.models import Subcontract, SubcontractClaim
from app.modules.subcontracts.router import router as subcontracts_router
from app.modules.subcontracts.schemas import SubcontractCreate
from app.runtime.modules import MODULES_BY_KEY, resolve_runtime_modules


def _paths(router) -> set[str]:
    return {route.path for route in router.routes if hasattr(route, "path")}


def test_india_execution_modules_are_runtime_selectable_with_commercial_dependency():
    for key in ("estimating", "procurement", "subcontracts", "scheduling"):
        assert key in MODULES_BY_KEY
        assert "commercial" in MODULES_BY_KEY[key].dependencies

    resolved = {manifest.key for manifest in resolve_runtime_modules("scheduling")}
    assert {"projects", "commercial", "scheduling"}.issubset(resolved)
    assert "estimating" not in resolved
    assert "procurement" not in resolved


def test_execution_modules_have_atomic_permissions_and_feature_entries():
    required = {
        "estimating.estimate.approve",
        "estimating.budget.approve",
        "procurement.requisition.approve",
        "procurement.purchase_order.issue",
        "procurement.receipt.receive",
        "subcontracts.contract.approve",
        "subcontracts.claim.certify",
        "scheduling.baseline.create",
        "scheduling.progress.update",
    }
    assert required.issubset(PERMISSIONS_BY_KEY)
    assert {"estimating", "procurement", "subcontracts", "scheduling"}.issubset(FEATURES_BY_KEY)


def test_client_create_schemas_cannot_inject_tenant_identity():
    for schema in (EstimateCreate, RequisitionCreate, SubcontractCreate, ScheduleCreate):
        assert "organization_id" not in schema.model_fields
        assert "project_id" not in schema.model_fields


def test_execution_tables_are_registered_when_models_are_imported():
    expected = {
        ProjectEstimate.__tablename__,
        ProjectBudget.__tablename__,
        PurchaseRequisition.__tablename__,
        PurchaseOrder.__tablename__,
        GoodsReceipt.__tablename__,
        Subcontract.__tablename__,
        SubcontractClaim.__tablename__,
        ProjectSchedule.__tablename__,
        ScheduleActivity.__tablename__,
        ScheduleBaseline.__tablename__,
    }
    assert expected.issubset(Base.metadata.tables)


def test_execution_routers_expose_real_project_scoped_contracts():
    assert "/projects/{project_id}/estimating/estimates" in _paths(estimating_router)
    assert "/projects/{project_id}/procurement/requisitions" in _paths(procurement_router)
    assert "/projects/{project_id}/procurement/purchase-orders" in _paths(procurement_router)
    assert "/projects/{project_id}/procurement/goods-receipts" in _paths(procurement_router)
    assert "/projects/{project_id}/subcontracts" in _paths(subcontracts_router)
    assert "/projects/{project_id}/subcontracts/claims" in _paths(subcontracts_router)
    assert "/projects/{project_id}/scheduling/schedules" in _paths(scheduling_router)


def test_search_bootstrap_registers_execution_projections():
    register_builtin_search_providers()
    for entity_type in (
        "project_estimate",
        "project_budget",
        "purchase_requisition",
        "purchase_order",
        "goods_receipt",
        "subcontract",
        "subcontract_claim",
        "project_schedule",
        "schedule_activity",
    ):
        assert search_projection_providers.contains(entity_type)
