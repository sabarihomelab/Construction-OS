import inspect
from pathlib import Path

from fastapi.routing import iter_route_contexts

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.financials import payables_service
from app.modules.financials.api import router as financials_router
from app.modules.financials.payables_models import (
    VendorBill,
    VendorBillLine,
    VendorBillReceiptMatch,
)
from app.modules.financials.payables_schemas import (
    VendorBillCreate,
    VendorBillLineCreate,
    VendorBillTransition,
)
from app.modules.financials.search import search_projection_providers


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables[table_name].foreign_key_constraints
    }


def test_vendor_payable_tables_are_registered() -> None:
    assert VendorBill.__tablename__ in Base.metadata.tables
    assert VendorBillLine.__tablename__ in Base.metadata.tables
    assert VendorBillReceiptMatch.__tablename__ in Base.metadata.tables


def test_vendor_bill_input_keeps_authoritative_po_fields_server_derived() -> None:
    create_fields = set(VendorBillCreate.model_fields)
    assert create_fields == {
        "purchase_order_id",
        "supplier_invoice_number",
        "invoice_date",
        "due_date",
        "notes",
    }
    forbidden = {
        "supplier_party_id",
        "currency_code",
        "subtotal",
        "tax_amount",
        "total_amount",
        "status",
        "match_status",
    }
    assert forbidden.isdisjoint(create_fields)


def test_vendor_bill_line_derives_construction_lineage_from_purchase_order() -> None:
    fields = set(VendorBillLineCreate.model_fields)
    assert "purchase_order_line_id" in fields
    assert "receipt_matches" in fields
    assert {
        "material_id",
        "wbs_code_id",
        "boq_item_id",
        "description",
        "unit_code",
        "po_unit_price_snapshot",
        "matched_quantity",
        "quantity_variance",
        "match_status",
    }.isdisjoint(fields)


def test_vendor_bill_receipt_matching_supports_multiple_grns() -> None:
    annotation = VendorBillLineCreate.model_fields["receipt_matches"].annotation
    assert getattr(annotation, "__origin__", None) is list
    targets = _fk_targets("vendor_bill_receipt_matches")
    assert (
        "goods_receipt_lines.id",
        "goods_receipt_lines.project_id",
        "goods_receipt_lines.organization_id",
    ) in targets
    assert (
        "vendor_bill_lines.id",
        "vendor_bill_lines.project_id",
        "vendor_bill_lines.organization_id",
    ) in targets


def test_variance_override_is_explicit_and_permissioned() -> None:
    assert "allow_variance_override" in VendorBillTransition.model_fields
    assert "reason" in VendorBillTransition.model_fields
    source = inspect.getsource(payables_service.submit_vendor_bill)
    assert "allow_variance_override" in source
    assert "Variance override requires a reason" in source


def test_vendor_bill_does_not_duplicate_material_job_cost_actual() -> None:
    source = inspect.getsource(payables_service)
    assert "ProjectCostEntry" not in source
    assert "ProjectCostSourceType" not in source
    assert "post_material_consumption" not in source


def test_payable_routes_are_composed() -> None:
    paths = {context.path for context in iter_route_contexts(financials_router.routes)}
    root = "/projects/{project_id}/financials/vendor-bills"
    assert root in paths
    assert f"{root}/{{vendor_bill_id}}/submit" in paths
    assert f"{root}/{{vendor_bill_id}}/approve" in paths
    assert f"{root}/{{vendor_bill_id}}/reject" in paths


def test_payable_permissions_are_in_static_catalog() -> None:
    expected = {
        "financials.payable.view",
        "financials.payable.create",
        "financials.payable.manage",
        "financials.payable.submit",
        "financials.payable.approve",
        "financials.payable.override",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)


def test_vendor_bill_has_approved_search_projection() -> None:
    assert search_projection_providers.contains("vendor_bill")


def test_vendor_payables_migration_follows_inventory_checkpoint() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260911_0047_vendor_payables.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260911_0047"' in migration
    assert 'down_revision: str | None = "20260911_0046"' in migration
    assert '"vendor_bills"' in migration
    assert '"vendor_bill_lines"' in migration
    assert '"vendor_bill_receipt_matches"' in migration
    assert '"uq_goods_receipt_lines_scope"' in migration
