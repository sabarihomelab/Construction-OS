import inspect

from app.main import app
from app.modules.commercial import measurement_control
from app.modules.commercial.measurement_control_schemas import (
    BOQMeasurementControlLine,
    BOQMeasurementControlSummary,
)


def test_boq_measurement_control_route_is_mounted() -> None:
    path = "/api/v1/projects/{project_id}/commercial/measurement-control/boq"
    assert path in app.openapi()["paths"]


def test_boq_measurement_control_exposes_cumulative_quantity_states() -> None:
    fields = set(BOQMeasurementControlLine.model_fields)
    assert {
        "boq_quantity",
        "measured_quantity",
        "submitted_quantity",
        "certified_quantity",
        "billed_quantity",
        "paid_quantity",
        "remaining_to_certify",
        "remaining_to_bill",
    } <= fields
    summary_fields = set(BOQMeasurementControlSummary.model_fields)
    assert {"total_boq_value", "total_certified_value", "total_billed_value", "total_paid_value"} <= summary_fields


def test_boq_measurement_control_uses_governed_states() -> None:
    source = inspect.getsource(measurement_control.build_boq_measurement_control)
    assert "BOQ.status == BOQStatus.APPROVED" in source
    assert "MeasurementStatus.DRAFT" in source
    assert "MeasurementStatus.SUBMITTED" in source
    assert "MeasurementStatus.CERTIFIED" in source
    assert "RABillStatus.SUBMITTED" in source
    assert "RABillStatus.CERTIFIED" in source
    assert "RABillStatus.PAID" in source
    assert "RABillStatus.CANCELLED" in source


def test_certification_ceiling_is_database_enforced() -> None:
    migration_path = "apps/api/migrations/versions/20260916_0062_boq_measurement_certification_limit.py"
    with open(migration_path, encoding="utf-8") as handle:
        migration = handle.read()
    assert "CREATE TRIGGER trg_boq_certified_measurement_limit" in migration
    assert "already_certified + NEW.quantity > boq_quantity" in migration
    assert "status = 'certified'" in migration
