from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.main import app
from app.modules.procurement.sourcing_models import RFQStatus, VendorQuotationStatus
from app.modules.procurement.sourcing_schemas import QuotationLineCreate, RFQCreate


def test_procurement_sourcing_routes_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    required = {
        "/api/v1/projects/{project_id}/procurement/rfqs",
        "/api/v1/projects/{project_id}/procurement/rfqs/{rfq_id}/vendors",
        "/api/v1/projects/{project_id}/procurement/rfqs/{rfq_id}/issue",
        "/api/v1/projects/{project_id}/procurement/rfqs/{rfq_id}/quotations",
        "/api/v1/projects/{project_id}/procurement/quotations/{quotation_id}/lines",
        "/api/v1/projects/{project_id}/procurement/quotations/{quotation_id}/submit",
        "/api/v1/projects/{project_id}/procurement/rfqs/{rfq_id}/comparison",
        "/api/v1/projects/{project_id}/procurement/rfqs/{rfq_id}/select-vendor",
        "/api/v1/projects/{project_id}/procurement/rfqs/{rfq_id}/purchase-order",
        "/api/v1/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/source",
    }
    assert required <= paths


def test_rfq_and_quotation_lifecycle_contract() -> None:
    assert RFQStatus.DRAFT.value == "draft"
    assert RFQStatus.ISSUED.value == "issued"
    assert RFQStatus.CLOSED.value == "closed"
    assert VendorQuotationStatus.DRAFT.value == "draft"
    assert VendorQuotationStatus.SUBMITTED.value == "submitted"
    assert VendorQuotationStatus.WITHDRAWN.value == "withdrawn"


def test_rfq_create_accepts_controlled_subset_of_requisition_lines() -> None:
    line_id = uuid4()
    payload = RFQCreate(
        requisition_id=uuid4(),
        title="Structural steel sourcing",
        requisition_line_ids=[line_id],
    )
    assert payload.requisition_line_ids == [line_id]


def test_quotation_line_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        QuotationLineCreate(
            rfq_line_id=uuid4(),
            line_number=1,
            quantity=Decimal("0"),
            unit_price=Decimal("100.00"),
        )


def test_quotation_line_preserves_explicit_tax_snapshot_fields() -> None:
    payload = QuotationLineCreate(
        rfq_line_id=uuid4(),
        line_number=1,
        quantity=Decimal("10"),
        unit_price=Decimal("125.50"),
        tax_code="GST-INPUT",
        tax_rate=Decimal("18"),
        lead_time_days=7,
    )
    assert payload.tax_rate == Decimal("18")
    assert payload.tax_code == "GST-INPUT"
    assert payload.lead_time_days == 7
    assert date.today() is not None
