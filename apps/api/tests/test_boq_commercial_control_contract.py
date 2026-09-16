import inspect

from app.main import app
from app.modules.financials import commercial_control
from app.modules.financials.commercial_control_schemas import (
    BOQCommercialControlLine,
    BOQCommercialControlSummary,
)


def test_boq_commercial_control_route_is_mounted() -> None:
    path = "/api/v1/projects/{project_id}/financials/commercial-control/boq"
    assert path in app.openapi()["paths"]


def test_boq_commercial_control_contract_exposes_budget_commitment_and_actuals() -> None:
    line_fields = set(BOQCommercialControlLine.model_fields)
    assert {
        "boq_item_id",
        "wbs_code_id",
        "boq_amount",
        "committed_amount",
        "actual_cost",
        "uncommitted_budget",
        "commitment_remaining",
        "budget_remaining",
    } <= line_fields

    summary_fields = set(BOQCommercialControlSummary.model_fields)
    assert {
        "total_boq_amount",
        "total_committed_amount",
        "total_actual_cost",
        "total_uncommitted_budget",
        "total_commitment_remaining",
        "total_budget_remaining",
    } <= summary_fields


def test_boq_commercial_control_uses_governed_sources() -> None:
    source = inspect.getsource(commercial_control.build_boq_commercial_control)

    assert "BOQ.status == BOQStatus.APPROVED" in source
    assert "ProjectCommitment.status != CommitmentStatus.CANCELLED" in source
    assert "ProjectCostEntry.status == ProjectCostStatus.POSTED" in source
    assert "ProjectCommitmentAllocation.boq_item_id" in source
    assert "ProjectCostAllocation.boq_item_id" in source


def test_boq_commercial_control_does_not_clamp_negative_variances() -> None:
    source = inspect.getsource(commercial_control.build_boq_commercial_control)

    assert "boq_amount - committed_amount" in source
    assert "committed_amount - actual_cost" in source
    assert "boq_amount - actual_cost" in source
    assert "max(" not in source
