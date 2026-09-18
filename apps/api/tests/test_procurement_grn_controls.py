from decimal import Decimal
from inspect import getsource

import pytest
from fastapi.routing import iter_route_contexts

from app.modules.equipment.inventory_service import record_goods_receipt_stock
from app.modules.procurement.router import router as procurement_router
from app.modules.procurement.schemas import GoodsReceiptLineUpdate
from app.modules.procurement.service import (
    ProcurementValidationError,
    _validate_goods_receipt_quantities,
    _validate_po_acceptance_limit,
)


def test_grn_can_leave_disposition_open_while_draft() -> None:
    _validate_goods_receipt_quantities(
        received=Decimal(10),
        accepted=Decimal(6),
        rejected=Decimal(0),
        remarks=None,
        require_full_disposition=False,
    )


def test_grn_requires_full_disposition_before_receiving() -> None:
    with pytest.raises(ProcurementValidationError, match="accepted or rejected"):
        _validate_goods_receipt_quantities(
            received=Decimal(10),
            accepted=Decimal(6),
            rejected=Decimal(0),
            remarks=None,
            require_full_disposition=True,
        )


def test_grn_rejection_requires_a_reason() -> None:
    with pytest.raises(ProcurementValidationError, match="Remarks are required"):
        _validate_goods_receipt_quantities(
            received=Decimal(10),
            accepted=Decimal(8),
            rejected=Decimal(2),
            remarks=None,
            require_full_disposition=True,
        )


def test_rejected_delivery_does_not_consume_po_acceptance_capacity() -> None:
    _validate_po_acceptance_limit(
        ordered_quantity=Decimal(10),
        previously_accepted=Decimal(0),
        accepted_quantity=Decimal(10),
    )


def test_accepted_quantity_cannot_exceed_po_quantity() -> None:
    with pytest.raises(ProcurementValidationError, match="remaining purchase order"):
        _validate_po_acceptance_limit(
            ordered_quantity=Decimal(10),
            previously_accepted=Decimal(8),
            accepted_quantity=Decimal(3),
        )


def test_grn_stock_uses_authoritative_po_boq_lineage() -> None:
    source = getsource(record_goods_receipt_stock)

    assert "boq_item_id=po_line.boq_item_id" in source
    assert "quantity=receipt_line.accepted_quantity" in source


def test_draft_grn_line_can_be_corrected_before_receive() -> None:
    paths = {context.path for context in iter_route_contexts(procurement_router.routes)}

    assert (
        "/projects/{project_id}/procurement/goods-receipts/"
        "{goods_receipt_id}/lines/{goods_receipt_line_id}"
    ) in paths
    assert GoodsReceiptLineUpdate.model_fields["expected_receipt_revision"].is_required()
