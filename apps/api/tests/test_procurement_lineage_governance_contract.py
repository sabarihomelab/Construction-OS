from inspect import getsource
from uuid import uuid4

import pytest

from app.modules.procurement.lineage import (
    _apply_boq_wbs_lineage,
    _apply_source_requisition_lineage,
)
from app.modules.procurement.router import add_purchase_order_line, add_requisition_line
from app.modules.procurement.service import ProcurementValidationError


def test_procurement_line_routes_use_governed_lineage_services() -> None:
    assert add_requisition_line.__module__ == "app.modules.procurement.lineage"
    assert add_purchase_order_line.__module__ == "app.modules.procurement.lineage"

    requisition_source = getsource(add_requisition_line)
    purchase_order_source = getsource(add_purchase_order_line)
    assert "await _apply_boq_lineage" in requisition_source
    assert "_apply_source_requisition_lineage" in purchase_order_source
    assert "await _apply_boq_lineage" in purchase_order_source


def test_requisition_line_inherits_wbs_from_boq_item() -> None:
    wbs_code_id = uuid4()
    values: dict[str, object] = {"wbs_code_id": None}

    _apply_boq_wbs_lineage(values, wbs_code_id=wbs_code_id)

    assert values["wbs_code_id"] == wbs_code_id


def test_requisition_line_rejects_wbs_that_conflicts_with_boq_item() -> None:
    values: dict[str, object] = {"wbs_code_id": uuid4()}

    with pytest.raises(
        ProcurementValidationError,
        match="WBS code must match the referenced BOQ item",
    ):
        _apply_boq_wbs_lineage(values, wbs_code_id=uuid4())


def test_purchase_order_line_inherits_source_requisition_dimensions() -> None:
    material_id = uuid4()
    wbs_code_id = uuid4()
    boq_item_id = uuid4()
    values: dict[str, object] = {
        "material_id": None,
        "wbs_code_id": None,
        "boq_item_id": None,
    }

    _apply_source_requisition_lineage(
        values,
        material_id=material_id,
        wbs_code_id=wbs_code_id,
        boq_item_id=boq_item_id,
    )

    assert values["material_id"] == material_id
    assert values["wbs_code_id"] == wbs_code_id
    assert values["boq_item_id"] == boq_item_id


@pytest.mark.parametrize(
    ("key", "expected_message"),
    [
        ("material_id", "Material must match the source requisition line"),
        ("wbs_code_id", "WBS code must match the source requisition line"),
        ("boq_item_id", "BOQ item must match the source requisition line"),
    ],
)
def test_purchase_order_line_rejects_source_lineage_conflicts(
    key: str,
    expected_message: str,
) -> None:
    source_ids = {
        "material_id": uuid4(),
        "wbs_code_id": uuid4(),
        "boq_item_id": uuid4(),
    }
    values: dict[str, object] = {key: uuid4()}

    with pytest.raises(ProcurementValidationError, match=expected_message):
        _apply_source_requisition_lineage(values, **source_ids)
