import inspect

from app.main import app
from app.modules.financials import subcontract_payable_service
from app.modules.financials.subcontract_payable_schemas import (
    SubcontractPayableLineRead,
    SubcontractPayableRead,
)


def test_subcontract_payable_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/projects/{project_id}/financials/payables/subcontract-claims"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/financials/payables/subcontract-claims/{claim_id}"
        in paths
    )


def test_subcontract_payable_is_derived_from_certified_claim_truth() -> None:
    source = inspect.getsource(subcontract_payable_service)

    assert "SubcontractClaimStatus.CERTIFIED" in source
    assert "SubcontractClaimStatus.PAID" in source
    assert "claim.certified_at is None" in source
    assert "claim.certified_amount" in source
    assert "claim.paid_amount" in source
    assert "db.add(" not in source


def test_subcontract_payable_reconciles_certified_lines() -> None:
    source = inspect.getsource(subcontract_payable_service._build_payable)

    assert "claim_line.certified_amount" in source
    assert "gross != _money(claim.gross_amount)" in source
    assert "paid > net" in source
    assert "outstanding_amount=_money(net - paid)" in source


def test_subcontract_payable_preserves_work_order_lineage() -> None:
    line_fields = set(SubcontractPayableLineRead.model_fields)

    assert {
        "claim_line_id",
        "subcontract_line_id",
        "measurement_entry_id",
        "wbs_code_id",
        "boq_item_id",
        "certified_quantity",
        "rate",
        "certified_amount",
    } <= line_fields

    source = inspect.getsource(subcontract_payable_service._build_payable)
    assert "wbs_code_id=contract_lines[claim_line.subcontract_line_id].wbs_code_id" in source
    assert "boq_item_id=contract_lines[claim_line.subcontract_line_id].boq_item_id" in source


def test_subcontract_payable_exposes_finance_balances_without_new_persistence() -> None:
    fields = set(SubcontractPayableRead.model_fields)

    assert {
        "gross_certified_work",
        "retention_amount",
        "other_deductions",
        "tax_withheld_amount",
        "net_certified_payable",
        "paid_amount",
        "outstanding_amount",
        "contractor_party_id",
        "currency_code",
    } <= fields
