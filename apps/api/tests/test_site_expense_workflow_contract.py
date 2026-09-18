from inspect import getsource

from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.financials import router as financials_router
from app.modules.financials.router import (
    decide_site_expense_approval as routed_site_expense_decision,
)
from app.modules.financials.router import (
    submit_site_expense_for_approval as routed_site_expense_submit,
)
from app.modules.financials.site_expense_workflow import (
    DEFAULT_APPROVER_ROLE_KEY,
    SITE_EXPENSE_ENTITY_TYPE,
    SITE_EXPENSE_WORKFLOW_KEY,
    ensure_site_expense_approval_workflow,
    submit_site_expense_for_approval,
)


def test_site_expense_workflow_uses_project_manager_default() -> None:
    assert SITE_EXPENSE_WORKFLOW_KEY == "financials.site_expense.approval"
    assert SITE_EXPENSE_ENTITY_TYPE == "site_expense"
    assert DEFAULT_APPROVER_ROLE_KEY == "project-manager"


def test_site_supervisor_can_capture_and_submit_site_expenses() -> None:
    role = ROLE_TEMPLATES_BY_KEY["site-supervisor"]

    assert {
        "financials.module.view",
        "financials.site_cash.view",
        "financials.site_expense.view",
        "financials.site_expense.create",
    } <= set(role.permission_keys)
    assert "financials.site_expense.approve" not in role.permission_keys
    assert "financials.site_expense.post" not in role.permission_keys


def test_project_manager_approves_site_expenses() -> None:
    role = ROLE_TEMPLATES_BY_KEY["project-manager"]

    assert {
        "financials.module.view",
        "financials.project_cost.view",
        "financials.site_expense.view",
        "financials.site_expense.approve",
    } <= set(role.permission_keys)


def test_accounts_finance_posts_approved_site_expenses() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert "financials.site_expense.view" in role.permission_keys
    assert "financials.site_expense.post" in role.permission_keys
    assert "financials.site_expense.approve" not in role.permission_keys


def test_site_expense_routes_use_shared_workflow_adapter() -> None:
    assert routed_site_expense_submit.__module__ == "app.modules.financials.site_expense_workflow"
    assert routed_site_expense_decision.__module__ == "app.modules.financials.site_expense_workflow"

    source = getsource(financials_router)
    assert "row = await submit_site_expense_for_approval(" in source
    assert "row = await decide_site_expense_approval(" in source


def test_site_expense_workflow_preserves_domain_submission_validation() -> None:
    source = getsource(submit_site_expense_for_approval)

    assert "expense = await submit_site_expense(" in source
    assert "expected_revision=expected_revision" in source


def test_site_expense_workflow_supports_rejection_and_resubmission() -> None:
    source = getsource(ensure_site_expense_approval_workflow)

    assert 'key="resubmit"' in source
    assert 'from_state_key="rejected"' in source
    assert 'key="reject"' in source
    assert "requires_reason=True" in source


def test_site_expense_posting_remains_separate_from_approval() -> None:
    source = getsource(financials_router.post_project_site_expense)

    assert '"financials.site_expense.post"' in source
    assert "post_site_expense(" in source
