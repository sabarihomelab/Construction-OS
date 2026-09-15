from app.main import app
from app.modules.commercial.boq_field_schemas import BOQFieldReferenceRead


def test_field_boq_reference_route_is_mounted_before_dynamic_detail_route() -> None:
    paths = list(app.openapi()["paths"])
    field_path = "/api/v1/projects/{project_id}/commercial/boqs/field-reference"
    detail_path = "/api/v1/projects/{project_id}/commercial/boqs/{boq_id}"
    assert field_path in paths
    assert detail_path in paths


def test_field_boq_reference_excludes_money_and_sensitive_commercial_fields() -> None:
    fields = set(BOQFieldReferenceRead.model_fields)
    assert {"quantity", "unit_code", "item_code", "description", "wbs_code_id"} <= fields
    assert fields.isdisjoint(
        {
            "rate",
            "amount",
            "currency_code",
            "total_amount",
            "approved_by_membership_id",
            "approved_at",
            "hsn_sac",
            "notes",
        }
    )
