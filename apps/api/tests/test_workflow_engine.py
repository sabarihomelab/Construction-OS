import pytest

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.workflows.models import WorkflowTransition
from app.modules.workflows.service import (
    WorkflowPermissionError,
    WorkflowValidationError,
    _validate_transition_access,
)


def test_workflow_tables_are_registered() -> None:
    expected = {
        "workflow_definitions",
        "workflow_versions",
        "workflow_states",
        "workflow_transitions",
        "workflow_instances",
        "workflow_transition_requests",
        "workflow_approval_tasks",
        "workflow_history_events",
    }
    assert expected.issubset(Base.metadata.tables)


def test_workflow_history_is_append_oriented() -> None:
    history = Base.metadata.tables["workflow_history_events"]
    assert "updated_at" not in history.c
    assert "instance_version" in history.c
    assert "occurred_at" in history.c


def test_workflow_version_and_runtime_references_are_tenant_consistent() -> None:
    versions = Base.metadata.tables["workflow_versions"]
    version_unique_names = {constraint.name for constraint in versions.constraints}
    assert "uq_workflow_versions_id_org" in version_unique_names

    instances = Base.metadata.tables["workflow_instances"]
    instance_fk_names = {constraint.name for constraint in instances.foreign_key_constraints}
    assert "fk_workflow_instances_version_org_definition" in instance_fk_names
    assert "fk_workflow_instances_current_state" in instance_fk_names

    approvals = Base.metadata.tables["workflow_approval_tasks"]
    approval_fk_names = {constraint.name for constraint in approvals.foreign_key_constraints}
    assert "fk_workflow_approval_tasks_request_org" in approval_fk_names


def test_workflow_admin_permissions_are_atomic() -> None:
    assert "admin.workflow.view" in PERMISSIONS_BY_KEY
    assert "admin.workflow.manage" in PERMISSIONS_BY_KEY


def _transition(**overrides) -> WorkflowTransition:
    values = {
        "key": "submit",
        "name": "Submit",
        "from_state_key": "draft",
        "to_state_key": "submitted",
        "required_permission_key": None,
        "requires_reason": False,
        "requires_step_up_mfa": False,
        "approval_policy": {},
        "conditions": {},
        "assignment_rule": {},
        "due_rule": {},
        "active": True,
    }
    values.update(overrides)
    return WorkflowTransition(**values)


def test_transition_requires_current_permission() -> None:
    transition = _transition(required_permission_key="finance.budget.view")
    with pytest.raises(WorkflowPermissionError):
        _validate_transition_access(
            transition,
            permission_keys=set(),
            reason=None,
            step_up_satisfied=False,
            conditions_satisfied=None,
            approval_completed=False,
        )


def test_transition_enforces_reason_and_step_up() -> None:
    transition = _transition(requires_reason=True, requires_step_up_mfa=True)
    with pytest.raises(WorkflowValidationError, match="reason"):
        _validate_transition_access(
            transition,
            permission_keys=set(),
            reason=None,
            step_up_satisfied=True,
            conditions_satisfied=None,
            approval_completed=False,
        )
    with pytest.raises(WorkflowPermissionError, match="Step-up"):
        _validate_transition_access(
            transition,
            permission_keys=set(),
            reason="Approved after review",
            step_up_satisfied=False,
            conditions_satisfied=None,
            approval_completed=False,
        )


def test_transition_with_domain_conditions_cannot_be_blindly_executed() -> None:
    transition = _transition(conditions={"domain_rule": "amount_within_limit"})
    with pytest.raises(WorkflowValidationError, match="conditions"):
        _validate_transition_access(
            transition,
            permission_keys=set(),
            reason=None,
            step_up_satisfied=False,
            conditions_satisfied=None,
            approval_completed=False,
        )


def test_approval_transition_cannot_bypass_completed_approval() -> None:
    transition = _transition(approval_policy={"mode": "sequential"})
    with pytest.raises(WorkflowValidationError, match="approval"):
        _validate_transition_access(
            transition,
            permission_keys=set(),
            reason=None,
            step_up_satisfied=False,
            conditions_satisfied=None,
            approval_completed=False,
        )
