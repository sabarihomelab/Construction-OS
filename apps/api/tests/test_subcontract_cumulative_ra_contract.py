import inspect

from app.main import app
from app.modules.subcontracts import cumulative_service
from app.modules.subcontracts.cumulative_schemas import (
    SubcontractClaimCumulativeLine,
    SubcontractClaimCumulativeRead,
)


def test_subcontract_cumulative_ra_route_is_mounted() -> None:
    path = "/api/v1/projects/{project_id}/subcontracts/{subcontract_id}/claims/{claim_id}/cumulative"
    assert path in app.openapi()["paths"]


def test_subcontract_cumulative_ra_exposes_previous_current_and_cumulative() -> None:
    fields = set(SubcontractClaimCumulativeLine.model_fields)
    assert {
        "previous_certified_quantity",
        "current_claimed_quantity",
        "current_certified_quantity",
        "cumulative_certified_quantity",
        "remaining_quantity",
        "previous_certified_amount",
        "current_certified_amount",
        "cumulative_certified_amount",
        "remaining_amount",
    } <= fields
    header_fields = set(SubcontractClaimCumulativeRead.model_fields)
    assert {
        "previous_certified_gross",
        "current_gross_amount",
        "current_certified_gross",
        "cumulative_certified_gross",
        "current_retention_amount",
        "current_other_deductions",
        "current_tax_withheld_amount",
        "current_net_certified",
        "current_paid_amount",
        "cumulative_paid_amount",
    } <= header_fields


def test_subcontract_cumulative_counts_only_certified_history() -> None:
    source = inspect.getsource(cumulative_service.build_subcontract_claim_cumulative)
    assert "SubcontractClaimStatus.CERTIFIED" in source
    assert "SubcontractClaimStatus.PAID" in source
    assert "SubcontractClaimLine.certified_quantity" in source
    assert "SubcontractClaimLine.certified_amount" in source
    assert "remaining_quantity=contract_quantity - cumulative_quantity" in source
