from inspect import getsource

from fastapi.routing import iter_route_contexts

from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.commercial import router
from app.modules.commercial.router import (
    decide_measurement_certification as routed_measurement_decision,
)
from app.modules.commercial.router import (
    decide_ra_bill_certification as routed_ra_bill_decision,
)
from app.modules.commercial.router import (
    submit_measurement_for_certification as routed_measurement_submit,
)
from app.modules.commercial.router import (
    submit_ra_bill_for_certification as routed_ra_bill_submit,
)
from app.modules.commercial.workflow import (
    DEFAULT_APPROVER_ROLE_KEY,
    MEASUREMENT_ENTITY_TYPE,
    MEASUREMENT_WORKFLOW_KEY,
    RA_BILL_ENTITY_TYPE,
    RA_BILL_WORKFLOW_KEY,
    ensure_measurement_certification_workflow,
    ensure_ra_bill_certification_workflow,
)


def test_commercial_workflows_use_simple_india_defaults() -> None:
    assert MEASUREMENT_WORKFLOW_KEY == "commercial.measurement.certification"
    assert MEASUREMENT_ENTITY_TYPE == "measurement_entry"
    assert RA_BILL_WORKFLOW_KEY == "commercial.ra_bill.certification"
    assert RA_BILL_ENTITY_TYPE == "ra_bill"
    assert DEFAULT_APPROVER_ROLE_KEY == "project-manager"


def test_qs_billing_engineer_prepares_and_submits_measurement_and_ra() -> None:
    role = ROLE_TEMPLATES_BY_KEY["qs-billing-engineer"]

    assert {
        "commercial.measurement.view",
        "commercial.measurement.create",
        "commercial.measurement.submit",
        "commercial.ra_bill.view",
        "commercial.ra_bill.create",
        "commercial.ra_bill.submit",
    } <= set(role.permission_keys)
    assert "commercial.measurement.certify" not in role.permission_keys
    assert "commercial.ra_bill.certify" not in role.permission_keys


def test_project_manager_certifies_measurement_and_ra_bill() -> None:
    role = ROLE_TEMPLATES_BY_KEY["project-manager"]

    assert "commercial.measurement.certify" in role.permission_keys
    assert "commercial.ra_bill.certify" in role.permission_keys


def test_accounts_finance_records_ra_bill_payment() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert "commercial.ra_bill.payment" in role.permission_keys
    assert "commercial.ra_bill.certify" not in role.permission_keys
    assert "commercial.ra_bill.payment" in PERMISSIONS_BY_KEY


def test_commercial_routes_use_shared_workflow_adapter() -> None:
    assert routed_measurement_submit.__module__ == "app.modules.commercial.workflow"
    assert routed_measurement_decision.__module__ == "app.modules.commercial.workflow"
    assert routed_ra_bill_submit.__module__ == "app.modules.commercial.workflow"
    assert routed_ra_bill_decision.__module__ == "app.modules.commercial.workflow"

    source = getsource(router)
    assert "row = await submit_measurement_for_certification(" in source
    assert "row = await decide_measurement_certification(" in source
    assert "row = await submit_ra_bill_for_certification(" in source
    assert "row = await decide_ra_bill_certification(" in source


def test_ra_bill_can_be_returned_for_revision_through_api() -> None:
    paths = {context.path for context in iter_route_contexts(router.router.routes)}

    assert (
        "/projects/{project_id}/commercial/ra-bills/{bill_id}/return-to-draft"
        in paths
    )


def test_measurement_workflow_supports_rejection_and_resubmission() -> None:
    source = getsource(ensure_measurement_certification_workflow)

    assert '"key": "resubmit"' in source
    assert '"from_state_key": "rejected"' in source
    assert '"key": "reject"' in source
    assert '"requires_reason": True' in source


def test_ra_bill_workflow_can_return_to_draft_for_correction() -> None:
    source = getsource(ensure_ra_bill_certification_workflow)

    assert '"key": "return_to_draft"' in source
    assert '"to_state_key": "draft"' in source
    assert '"requires_reason": True' in source


def test_ra_bill_payment_route_uses_payment_permission() -> None:
    source = getsource(router.mark_ra_bill_paid_route)

    assert 'permission_key="commercial.ra_bill.payment"' in source
