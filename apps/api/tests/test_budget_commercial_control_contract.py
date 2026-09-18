import inspect

from app.main import app
from app.modules.financials import budget_control
from app.modules.financials.budget_control_schemas import (
    BudgetCommercialControlLine,
    BudgetCommercialControlSummary,
)


def test_budget_commercial_control_route_is_mounted() -> None:
    path = "/api/v1/projects/{project_id}/financials/commercial-control/budget"
    assert path in app.openapi()["paths"]


def test_budget_control_contract_uses_approved_budget_as_cost_baseline() -> None:
    source = inspect.getsource(budget_control.build_budget_commercial_control)

    assert "ProjectBudget.status == BudgetStatus.APPROVED" in source
    assert "BudgetLine.budget_id == budget.id" in source
    assert "ProjectCommitment.status != CommitmentStatus.CANCELLED" in source
    assert "ProjectCostEntry.status == ProjectCostStatus.POSTED" in source
    assert "ProjectCommitment.currency_code != currency_code" in source
    assert "ProjectCostEntry.currency_code != currency_code" in source


def test_budget_control_maps_operational_sources_to_budget_dimensions() -> None:
    assert budget_control.COMMITMENT_TO_BUDGET_CATEGORY
    assert budget_control.COST_HEAD_TO_BUDGET_CATEGORY

    line_fields = set(BudgetCommercialControlLine.model_fields)
    assert {
        "wbs_code_id",
        "category",
        "has_budget_line",
        "budget_amount",
        "committed_amount",
        "actual_cost",
        "forecast_exposure",
        "uncommitted_budget",
        "commitment_remaining",
        "budget_remaining_to_actual",
        "forecast_variance",
    } <= line_fields


def test_budget_control_surfaces_allocation_coverage() -> None:
    summary_fields = set(BudgetCommercialControlSummary.model_fields)
    assert {
        "control_coverage_complete",
        "unallocated_commitment_amount",
        "unallocated_actual_cost",
        "total_budget_amount",
        "total_committed_amount",
        "total_actual_cost",
        "total_forecast_exposure",
        "total_forecast_variance",
    } <= summary_fields

    source = inspect.getsource(budget_control.build_budget_commercial_control)
    assert "has_budget_line" in source
    assert "unallocated_commitment_amount" in source
    assert "unallocated_actual_cost" in source


def test_budget_control_preserves_negative_variances() -> None:
    source = inspect.getsource(budget_control.build_budget_commercial_control)

    assert "budget_amount - committed_amount" in source
    assert "committed_amount - actual_cost" in source
    assert "budget_amount - actual_cost" in source
    assert "budget_amount - forecast_exposure" in source
    assert "max(committed_amount, actual_cost)" in source
