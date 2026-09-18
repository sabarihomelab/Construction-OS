import pytest
from fastapi.routing import iter_route_contexts

from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.procurement.router import (
    decide_requisition_approval as routed_requisition_decision,
)
from app.modules.procurement.router import router as procurement_router
from app.modules.procurement.router import (
    submit_requisition_for_approval as routed_requisition_submit,
)
from app.modules.procurement.service import ProcurementValidationError
from app.modules.procurement.workflow import (
    DEFAULT_APPROVER_ROLE_KEY,
    REQUISITION_ENTITY_TYPE,
    REQUISITION_WORKFLOW_KEY,
    _approval_assignees,
)
from app.modules.workflows.models import ApprovalAssigneeType


def test_requisition_workflow_has_simple_india_default():
    assert REQUISITION_WORKFLOW_KEY == "procurement.requisition.approval"
    assert REQUISITION_ENTITY_TYPE == "purchase_requisition"
    assert DEFAULT_APPROVER_ROLE_KEY == "project-manager"


def test_project_manager_template_can_approve_requisitions():
    project_manager = ROLE_TEMPLATES_BY_KEY["project-manager"]

    assert "procurement.module.view" in project_manager.permission_keys
    assert "procurement.requisition.view" in project_manager.permission_keys
    assert "procurement.requisition.approve" in project_manager.permission_keys


def test_assignment_rule_supports_configurable_sequential_approvers():
    assignees = _approval_assignees(
        {
            "assignees": [
                {
                    "assignee_type": "project_role",
                    "assignee_id": "project-manager",
                    "sequence": 1,
                },
                {
                    "assignee_type": "role",
                    "assignee_id": "company-management",
                    "sequence": 2,
                },
            ]
        }
    )

    assert [(item.assignee_type, item.assignee_id, item.sequence) for item in assignees] == [
        (ApprovalAssigneeType.PROJECT_ROLE, "project-manager", 1),
        (ApprovalAssigneeType.ROLE, "company-management", 2),
    ]


def test_assignment_rule_rejects_missing_approvers():
    with pytest.raises(ProcurementValidationError, match="no configured assignee"):
        _approval_assignees({})


def test_requisition_routes_use_shared_workflow_adapter():
    assert routed_requisition_submit.__module__ == "app.modules.procurement.workflow"
    assert routed_requisition_decision.__module__ == "app.modules.procurement.workflow"


def test_rejected_requisition_can_be_revised_through_api_contract():
    paths = {context.path for context in iter_route_contexts(procurement_router.routes)}

    assert "/projects/{project_id}/procurement/requisitions/{requisition_id}/revise" in paths
