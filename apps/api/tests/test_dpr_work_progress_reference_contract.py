from app.modules.field.dpr_reference_router import router as dpr_reference_router
from app.modules.field.dpr_reference_schemas import (
    DPRWorkProgressBOQItemReferenceRead,
    DPRWorkProgressReferenceRead,
)


def test_dpr_work_progress_reference_endpoint_is_registered() -> None:
    paths = {route.path for route in dpr_reference_router.routes}
    assert "/projects/{project_id}/daily-reports/work-progress/references" in paths


def test_dpr_work_progress_reference_contract_excludes_financial_values() -> None:
    item_fields = set(DPRWorkProgressBOQItemReferenceRead.model_fields)
    response_fields = set(DPRWorkProgressReferenceRead.model_fields)

    assert response_fields == {"wbs_codes", "boq_items"}
    assert {
        "id",
        "boq_id",
        "boq_code",
        "boq_name",
        "wbs_code_id",
        "item_code",
        "description",
        "unit_code",
    } == item_fields
    assert "rate" not in item_fields
    assert "amount" not in item_fields
    assert "quantity" not in item_fields
    assert "currency_code" not in item_fields
