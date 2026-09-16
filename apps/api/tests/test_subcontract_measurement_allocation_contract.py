from inspect import getsource

from app.modules.subcontracts import claim_service, router


def test_claim_entry_checks_remaining_certified_measurement_quantity() -> None:
    source = getsource(claim_service._validate_measurement_allocation)

    assert "_measurement_allocated_quantity" in source
    assert "allocated + claimed_quantity > measurement.quantity" in source
    assert "Measurement BOQ item does not match the work-order line" in source


def test_claim_certification_rechecks_work_order_and_measurement_limits() -> None:
    source = getsource(claim_service.certify_claim)

    assert ".with_for_update()" in source
    assert "_line_certified_quantity" in source
    assert "previously_certified + current_quantity > contract_line.quantity" in source
    assert "current_by_measurement" in source
    assert "lock_measurement=True" in source


def test_subcontract_routes_use_hardened_claim_service() -> None:
    source = getsource(router)

    assert "from app.modules.subcontracts.claim_service import add_claim_line, certify_claim" in source
