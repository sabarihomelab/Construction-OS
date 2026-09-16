import inspect

from app.main import app
from app.modules.financials import receivable_service
from app.modules.financials.models import ClientInvoiceStatus, ClientReceiptStatus
from app.modules.financials.receivable_schemas import ClientInvoiceDetailRead, ClientReceiptCreate


def test_client_receivable_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/projects/{project_id}/financials/receivables/invoices/from-ra-bill" in paths
    assert "/api/v1/projects/{project_id}/financials/receivables/invoices/{invoice_id}/issue" in paths
    assert "/api/v1/projects/{project_id}/financials/receivables/receipts" in paths


def test_client_invoice_requires_certified_ra_and_project_client() -> None:
    source = inspect.getsource(receivable_service.create_client_invoice_from_ra_bill)
    assert "RABillStatus.CERTIFIED" in source
    assert "ProjectPartyAssignment.role == ProjectPartyRole.CLIENT" in source
    assert "ClientInvoice.source_ra_bill_id == ra_bill_id" in source
    assert "ClientInvoice.status != ClientInvoiceStatus.CANCELLED" in source
    assert "RABillLine" in source
    assert "BOQItem" in source


def test_client_invoice_preserves_commercial_lineage() -> None:
    source = inspect.getsource(receivable_service.create_client_invoice_from_ra_bill)
    assert "wbs_code_id=item.wbs_code_id" in source
    assert "boq_item_id=item.id" in source
    assert "quantity=bill_line.current_quantity" in source
    assert "rate=bill_line.rate" in source


def test_receipts_cannot_over_allocate_outstanding_invoice() -> None:
    source = inspect.getsource(receivable_service.post_client_receipt)
    assert "ClientInvoiceStatus.ISSUED" in source
    assert "ClientInvoiceStatus.PARTIALLY_PAID" in source
    assert "amount > outstanding" in source
    assert "ClientReceiptStatus.POSTED" in source
    assert "ClientInvoiceStatus.PAID" in source


def test_receipt_schema_requires_full_unique_allocation() -> None:
    fields = set(ClientReceiptCreate.model_fields)
    assert {"client_party_id", "amount", "currency_code", "allocations"} <= fields
    assert "received_amount" in ClientInvoiceDetailRead.model_fields
    assert "outstanding_amount" in ClientInvoiceDetailRead.model_fields
    assert ClientReceiptStatus.POSTED.value == "posted"
    assert ClientInvoiceStatus.PAID.value == "paid"
