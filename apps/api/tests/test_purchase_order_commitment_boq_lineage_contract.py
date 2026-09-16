from inspect import getsource

from app.modules.financials.commitment_feeds import post_purchase_order_commitment


def test_purchase_order_commitment_uses_po_line_boq_reference() -> None:
    source = getsource(post_purchase_order_commitment)

    assert "boq_item_id=line.boq_item_id" in source
    assert "PurchaseRequisitionLine" not in source
    assert "requisition_lines" not in source
