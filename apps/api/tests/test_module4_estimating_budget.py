from decimal import Decimal

from fastapi import FastAPI

from app.db import model_registry as _model_registry  # noqa: F401
from app.db.base import Base
from app.modules.configuration.registry import CONFIGURATION_DEFINITIONS_BY_KEY
from app.modules.estimating.governed_router import router
from app.modules.estimating.governed_service import rate_breakdown
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.runtime.modules import MODULES_BY_KEY


def _paths() -> dict[str, dict[str, object]]:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    return application.openapi()["paths"]


def test_estimating_feature_and_runtime_use_governed_surface() -> None:
    feature = FEATURES_BY_KEY["estimating"]
    manifest = MODULES_BY_KEY["estimating"]

    assert feature.release_state == FeatureReleaseState.AVAILABLE
    assert feature.route == "/estimating"
    assert manifest.dependencies == ("commercial",)
    assert manifest.api_router == "app.modules.estimating.governed_router:router"


def test_estimating_api_exposes_approval_and_history_workflows() -> None:
    paths = _paths()
    estimate = "/api/v1/projects/{project_id}/estimating/estimates/{estimate_id}"
    budget = "/api/v1/projects/{project_id}/estimating/budgets/{budget_id}"

    assert estimate in paths
    assert f"{estimate}/copy-boq-items" in paths
    assert f"{estimate}/submit" in paths
    assert f"{estimate}/approve" in paths
    assert f"{estimate}/revise" in paths
    assert f"{estimate}/approvals" in paths
    assert f"{budget}/approve" in paths
    assert f"{budget}/approvals" in paths
    assert "/api/v1/projects/{project_id}/estimating/estimate-items/{item_id}/rate-analysis" in paths


def test_estimating_history_models_are_registered() -> None:
    assert "estimate_approval_snapshots" in Base.metadata.tables
    assert "estimate_revision_links" in Base.metadata.tables
    assert "budget_approval_snapshots" in Base.metadata.tables


def test_rate_breakdown_separates_project_cost_from_profit() -> None:
    result = rate_breakdown(
        Decimal("150.00"),
        Decimal(10),
        Decimal(20),
        Decimal(10),
    )

    assert result["base_rate"] == Decimal("150.00")
    assert result["wastage_amount"] == Decimal("15.00")
    assert result["overhead_amount"] == Decimal("33.00")
    assert result["cost_rate"] == Decimal("198.00")
    assert result["profit_amount"] == Decimal("19.80")
    assert result["selling_rate"] == Decimal("217.80")
    assert result["selling_rate"] > result["cost_rate"]


def test_estimating_company_defaults_are_configurable_not_transaction_hardcoded() -> None:
    for key in (
        "estimating.rate_analysis.default_wastage_percent",
        "estimating.rate_analysis.default_overhead_percent",
        "estimating.rate_analysis.default_profit_percent",
    ):
        definition = CONFIGURATION_DEFINITIONS_BY_KEY[key]
        assert definition.module_key == "estimating"
        assert definition.value_type.value == "decimal"
        assert definition.configurable is True


def test_budget_snapshot_fk_points_to_estimate_approval_snapshot() -> None:
    table = Base.metadata.tables["budget_approval_snapshots"]
    targets = {
        foreign_key.target_fullname
        for foreign_key in table.c.estimate_snapshot_id.foreign_keys
    }
    assert "estimate_approval_snapshots.id" in targets
