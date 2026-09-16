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


def test_boq_commercial_control_contract_separates_cost_and_billing_baselines() -> None:
    line_fields = set(BOQCommercialControlLine.model_fields)
    assert {
        "boq_item_id",
        "wbs_code_id",
        "boq_amount",
        "approved_estimate_amount",
        "committed_amount",
        "actual_cost",
        "certified_billed_amount",
        "uncommitted_estimate",
        "commitment_remaining",
        "estimate_remaining",
        "unbilled_boq_value",
    } <= line_fields

    summary_fields = set(BOQCommercialControlSummary.model_fields)
    assert {
        "estimate_coverage_complete",
        "total_boq_amount",
        "total_approved_estimate_amount",
        "total_committed_amount",
        "total_actual_cost",
        "total_certified_billed_amount",
        "total_uncommitted_estimate",
        "total_commitment_remaining",
        "total_estimate_remaining",
        "total_unbilled_boq_value",
    } <= summary_fields


def test_boq_commercial_control_uses_governed_sources() -> None:
    source = inspect.getsource(commercial_control.build_boq_commercial_control)

    assert "BOQ.status == BOQStatus.APPROVED" in source
    assert "ProjectEstimate.status == EstimateStatus.APPROVED" in source
    assert "EstimateItem.boq_item_id" in source
    assert "ProjectCommitment.status != CommitmentStatus.CANCELLED" in source
    assert "ProjectCostEntry.status == ProjectCostStatus.POSTED" in source
    assert "RABill.status.in_({RABillStatus.CERTIFIED, RABillStatus.PAID})" in source
    assert "ProjectCommitmentAllocation.boq_item_id" in source
    assert "ProjectCostAllocation.boq_item_id" in source
    assert "RABillLine.boq_item_id" in source


def test_boq_commercial_control_does_not_mix_boq_value_with_cost_budget() -> None:
    source = inspect.getsource(commercial_control.build_boq_commercial_control)

    assert "approved_estimate_amount - committed_amount" in source
    assert "approved_estimate_amount - actual_cost" in source
    assert "boq_amount - certified_billed_amount" in source
    assert "boq_amount - committed_amount" not in source
    assert "boq_amount - actual_cost" not in source
    assert "max(" not in source
