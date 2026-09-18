from inspect import getsource

from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.financials import payables_router
from app.modules.financials.payables_router import (
    decide_vendor_bill_approval as routed_vendor_bill_decision,
)
from app.modules.financials.payables_router import (
    submit_vendor_bill_for_approval as routed_vendor_bill_submit,
)
from app.modules.financials.payables_workflow import (
    DEFAULT_APPROVER_ROLE_KEY,
    VENDOR_BILL_ENTITY_TYPE,
    VENDOR_BILL_WORKFLOW_KEY,
    ensure_vendor_bill_approval_workflow,
    submit_vendor_bill_for_approval,
)


def test_vendor_bill_workflow_uses_simple_company_approval_default() -> None:
    assert VENDOR_BILL_WORKFLOW_KEY == "financials.vendor_bill.approval"
    assert VENDOR_BILL_ENTITY_TYPE == "vendor_bill"
    assert DEFAULT_APPROVER_ROLE_KEY == "company-management"


def test_accounts_finance_prepares_and_submits_vendor_bills() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert {
        "financials.payable.view",
        "financials.payable.create",
        "financials.payable.manage",
        "financials.payable.submit",
    } <= set(role.permission_keys)
    assert "financials.payable.approve" not in role.permission_keys


def test_company_management_approves_vendor_bills() -> None:
    role = ROLE_TEMPLATES_BY_KEY["company-management"]

    assert "financials.payable.view" in role.permission_keys
    assert "financials.payable.approve" in role.permission_keys


def test_vendor_bill_routes_use_shared_workflow_adapter() -> None:
    assert routed_vendor_bill_submit.__module__ == "app.modules.financials.payables_workflow"
    assert routed_vendor_bill_decision.__module__ == "app.modules.financials.payables_workflow"

    source = getsource(payables_router)
    assert "bill = await submit_vendor_bill_for_approval(" in source
    assert "bill = await decide_vendor_bill_approval(" in source


def test_workflow_preserves_three_way_match_submission_rules() -> None:
    source = getsource(submit_vendor_bill_for_approval)

    assert "return await submit_vendor_bill(" not in source
    assert "bill = await submit_vendor_bill(" in source
    assert "allow_variance_override=allow_variance_override" in source


def test_vendor_bill_workflow_supports_rejection_and_resubmission() -> None:
    source = getsource(ensure_vendor_bill_approval_workflow)

    assert 'key="resubmit"' in source
    assert 'from_state_key="rejected"' in source
    assert 'key="reject"' in source
    assert "requires_reason=True" in source


def test_variance_override_permission_check_stays_at_api_boundary() -> None:
    source = getsource(payables_router.submit_vendor_bill_route)

    assert 'if payload.allow_variance_override:' in source
    assert '"financials.payable.override"' in source
