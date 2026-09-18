from inspect import getsource

from fastapi.routing import iter_route_contexts

from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.subcontracts import router
from app.modules.subcontracts.router import (
    decide_claim_certification as routed_claim_decision,
)
from app.modules.subcontracts.router import (
    decide_contract_approval as routed_contract_decision,
)
from app.modules.subcontracts.router import (
    submit_claim_for_certification as routed_claim_submit,
)
from app.modules.subcontracts.router import (
    submit_contract_for_approval as routed_contract_submit,
)
from app.modules.subcontracts.workflow import (
    CLAIM_ENTITY_TYPE,
    CLAIM_WORKFLOW_KEY,
    CONTRACT_ENTITY_TYPE,
    CONTRACT_WORKFLOW_KEY,
    DEFAULT_APPROVER_ROLE_KEY,
    ensure_claim_certification_workflow,
    ensure_contract_approval_workflow,
)


def test_subcontract_workflows_use_simple_india_defaults() -> None:
    assert CONTRACT_WORKFLOW_KEY == "subcontracts.contract.approval"
    assert CONTRACT_ENTITY_TYPE == "subcontract"
    assert CLAIM_WORKFLOW_KEY == "subcontracts.claim.certification"
    assert CLAIM_ENTITY_TYPE == "subcontract_claim"
    assert DEFAULT_APPROVER_ROLE_KEY == "project-manager"


def test_qs_billing_engineer_prepares_and_submits_subcontract_records() -> None:
    role = ROLE_TEMPLATES_BY_KEY["qs-billing-engineer"]

    assert {
        "subcontracts.module.view",
        "subcontracts.contract.view",
        "subcontracts.contract.create",
        "subcontracts.contract.manage",
        "subcontracts.contract.submit",
        "subcontracts.claim.view",
        "subcontracts.claim.create",
        "subcontracts.claim.manage",
        "subcontracts.claim.submit",
    } <= set(role.permission_keys)
    assert "subcontracts.contract.approve" not in role.permission_keys
    assert "subcontracts.claim.certify" not in role.permission_keys


def test_project_manager_approves_work_orders_and_certifies_ra_claims() -> None:
    role = ROLE_TEMPLATES_BY_KEY["project-manager"]

    assert {
        "subcontracts.module.view",
        "subcontracts.contract.view",
        "subcontracts.contract.approve",
        "subcontracts.contract.issue",
        "subcontracts.claim.view",
        "subcontracts.claim.certify",
    } <= set(role.permission_keys)


def test_accounts_finance_can_record_certified_claim_payment() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert {
        "subcontracts.module.view",
        "subcontracts.contract.view",
        "subcontracts.claim.view",
        "subcontracts.claim.payment",
    } <= set(role.permission_keys)


def test_subcontract_routes_use_shared_workflow_adapter() -> None:
    assert routed_contract_submit.__module__ == "app.modules.subcontracts.workflow"
    assert routed_contract_decision.__module__ == "app.modules.subcontracts.workflow"
    assert routed_claim_submit.__module__ == "app.modules.subcontracts.workflow"
    assert routed_claim_decision.__module__ == "app.modules.subcontracts.workflow"

    source = getsource(router)
    assert "row = await submit_contract_for_approval(" in source
    assert "row = await decide_contract_approval(" in source
    assert "row = await submit_claim_for_certification(" in source
    assert "row = await decide_claim_certification(" in source


def test_work_order_can_be_returned_for_revision_through_api() -> None:
    paths = {context.path for context in iter_route_contexts(router.router.routes)}

    assert (
        "/projects/{project_id}/subcontracts/{subcontract_id}/return-to-draft"
        in paths
    )


def test_claim_workflow_supports_rejection_and_resubmission() -> None:
    source = getsource(ensure_claim_certification_workflow)

    assert '"key": "resubmit"' in source
    assert '"from_state_key": "rejected"' in source
    assert '"key": "reject"' in source
    assert '"requires_reason": True' in source


def test_contract_workflow_rejection_returns_to_editable_draft() -> None:
    source = getsource(ensure_contract_approval_workflow)

    assert '"key": "return_to_draft"' in source
    assert '"to_state_key": "draft"' in source
    assert '"requires_reason": True' in source
