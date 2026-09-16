from decimal import Decimal
from inspect import getsource
from uuid import uuid4

from sqlalchemy import inspect

from app.modules.procurement.models import PurchaseOrderLine
from app.modules.procurement.schemas import PurchaseOrderLineCreate, PurchaseOrderLineRead
from app.modules.procurement.service import add_purchase_order_line


def test_purchase_order_line_persists_boq_reference() -> None:
    mapper = inspect(PurchaseOrderLine)
    assert "boq_item_id" in {column.key for column in mapper.columns}

    foreign_key_names = {
        constraint.name
        for constraint in PurchaseOrderLine.__table__.foreign_key_constraints
    }
    assert "fk_purchase_order_lines_boq_scope" in foreign_key_names


def test_purchase_order_line_api_exposes_boq_reference() -> None:
    boq_item_id = uuid4()
    payload = PurchaseOrderLineCreate(
        line_number=1,
        boq_item_id=boq_item_id,
        description="TMT reinforcement steel",
        unit_code="KG",
        quantity=Decimal("100.0000"),
        unit_price=Decimal("62.50"),
    )

    assert payload.boq_item_id == boq_item_id
    assert "boq_item_id" in PurchaseOrderLineRead.model_fields


def test_purchase_order_line_derives_boq_from_source_requisition_line() -> None:
    source = getsource(add_purchase_order_line)

    assert 'data["boq_item_id"] = req_line.boq_item_id' in source
    assert '"BOQ item must match the source requisition line"' in source
    assert "boq_item_id=data.get" in source
