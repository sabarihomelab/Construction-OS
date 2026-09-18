from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.models import MembershipRole, Role
from app.modules.projects.models import (
    ProjectMembership,
    ProjectMembershipStatus,
    ProjectRoleAssignment,
)
from app.modules.subcontracts.claim_service import certify_claim
from app.modules.subcontracts.models import (
    Subcontract,
    SubcontractClaim,
    SubcontractClaimStatus,
    SubcontractStatus,
)
from app.modules.subcontracts.review import reject_claim
from app.modules.subcontracts.service import (
    SubcontractConflictError,
    SubcontractValidationError,
    submit_claim,
    transition_subcontract,
)
from app.modules.workflows.approvals import (
    decide_approval_task,
    execute_approved_transition_request,
)
from app.modules.workflows.models import (
    ApprovalAssigneeType,
    ApprovalTaskStatus,
    TransitionRequestStatus,
    WorkflowApprovalTask,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowState,
    WorkflowStateKind,
    WorkflowTransition,
    WorkflowTransitionRequest,
    WorkflowVersion,
    WorkflowVersionStatus,
)
from app.modules.workflows.service import (
    ApprovalAssignee,
    WorkflowConflictError,
    WorkflowPermissionError,
    WorkflowValidationError,
    execute_transition,
    publish_workflow_version,
    request_approval_transition,
    start_workflow_instance,
)

CONTRACT_WORKFLOW_KEY = "subcontracts.contract.approval"
CONTRACT_ENTITY_TYPE = "subcontract"
CLAIM_WORKFLOW_KEY = "subcontracts.claim.certification"
CLAIM_ENTITY_TYPE = "subcontract_claim"
DEFAULT_APPROVER_ROLE_KEY = "project-manager"


async def _ensure_workflow_definition(
    db: AsyncSession,
    *,
    organization_id: UUID,
    key: str,
    entity_type: str,
    name: str,
    states: list[tuple[str, str, WorkflowStateKind]],
    transitions: list[dict[str, object]],
    actor_user_id: UUID,
    session_id: UUID | None,
) -> WorkflowDefinition:
    definition = await db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.organization_id == organization_id,
            WorkflowDefinition.key == key,
        )
    )
    if definition is not None:
        if not definition.active or definition.current_version < 1:
            raise SubcontractValidationError(
                f"{name} workflow exists but is not published"
            )
        return definition

    definition = WorkflowDefinition(
        organization_id=organization_id,
        key=key,
        entity_type=entity_type,
        name=name,
        description=f"Default India-first {name.lower()} workflow.",
        current_version=0,
        active=True,
        created_by_user_id=actor_user_id,
    )
    db.add(definition)
    await db.flush()

    version = WorkflowVersion(
        organization_id=organization_id,
        definition_id=definition.id,
        version=1,
        status=WorkflowVersionStatus.DRAFT,
        configuration={"template": "india-default", "simple_by_default": True},
    )
    db.add(version)
    await db.flush()

    for display_order, (state_key, label, kind) in enumerate(states, start=1):
        db.add(
            WorkflowState(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key=state_key,
                label=label,
                kind=kind,
                display_order=display_order * 10,
            )
        )

    for transition_values in transitions:
        db.add(
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                **transition_values,
            )
        )
    await db.flush()

    await publish_workflow_version(
        db,
        workflow_version_id=version.id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return definition


def _default_assignment_rule() -> dict[str, object]:
    return {
        "assignees": [
            {
                "assignee_type": ApprovalAssigneeType.PROJECT_ROLE.value,
                "assignee_id": DEFAULT_APPROVER_ROLE_KEY,
                "sequence": 1,
            }
        ]
    }


async def ensure_contract_approval_workflow(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WorkflowDefinition:
    return await _ensure_workflow_definition(
        db,
        organization_id=organization_id,
        key=CONTRACT_WORKFLOW_KEY,
        entity_type=CONTRACT_ENTITY_TYPE,
        name="Subcontract Work Order Approval",
        states=[
            ("draft", "Draft", WorkflowStateKind.INITIAL),
            ("submitted", "Submitted", WorkflowStateKind.ACTIVE),
            ("approved", "Approved", WorkflowStateKind.COMPLETED),
        ],
        transitions=[
            {
                "key": "submit",
                "name": "Submit work order",
                "from_state_key": "draft",
                "to_state_key": "submitted",
                "required_permission_key": "subcontracts.contract.submit",
            },
            {
                "key": "approve",
                "name": "Approve work order",
                "from_state_key": "submitted",
                "to_state_key": "approved",
                "approval_policy": {"mode": "sequential"},
                "assignment_rule": _default_assignment_rule(),
            },
            {
                "key": "return_to_draft",
                "name": "Return work order to draft",
                "from_state_key": "submitted",
                "to_state_key": "draft",
                "required_permission_key": "subcontracts.contract.approve",
                "requires_reason": True,
            },
        ],
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def ensure_claim_certification_workflow(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WorkflowDefinition:
    return await _ensure_workflow_definition(
        db,
        organization_id=organization_id,
        key=CLAIM_WORKFLOW_KEY,
        entity_type=CLAIM_ENTITY_TYPE,
        name="Subcontract RA Claim Certification",
        states=[
            ("draft", "Draft", WorkflowStateKind.INITIAL),
            ("submitted", "Submitted", WorkflowStateKind.ACTIVE),
            ("rejected", "Rejected", WorkflowStateKind.ACTIVE),
            ("certified", "Certified", WorkflowStateKind.COMPLETED),
        ],
        transitions=[
            {
                "key": "submit",
                "name": "Submit RA claim",
                "from_state_key": "draft",
                "to_state_key": "submitted",
                "required_permission_key": "subcontracts.claim.submit",
            },
            {
                "key": "resubmit",
                "name": "Resubmit RA claim",
                "from_state_key": "rejected",
                "to_state_key": "submitted",
                "required_permission_key": "subcontracts.claim.submit",
            },
            {
                "key": "certify",
                "name": "Certify RA claim",
                "from_state_key": "submitted",
                "to_state_key": "certified",
                "approval_policy": {"mode": "sequential"},
                "assignment_rule": _default_assignment_rule(),
            },
            {
                "key": "reject",
                "name": "Reject RA claim",
                "from_state_key": "submitted",
                "to_state_key": "rejected",
                "required_permission_key": "subcontracts.claim.certify",
                "requires_reason": True,
            },
        ],
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


def _approval_assignees(assignment_rule: Mapping[str, object]) -> list[ApprovalAssignee]:
    raw_assignees = assignment_rule.get("assignees")
    if not isinstance(raw_assignees, list) or not raw_assignees:
        raise SubcontractValidationError("Approval workflow has no configured assignee")

    assignees: list[ApprovalAssignee] = []
    for raw in raw_assignees:
        if not isinstance(raw, dict):
            raise SubcontractValidationError("Approval workflow assignee is invalid")
        raw_type = raw.get("assignee_type")
        raw_id = raw.get("assignee_id")
        raw_sequence = raw.get("sequence", 1)
        if not isinstance(raw_type, str) or not isinstance(raw_id, str):
            raise SubcontractValidationError("Approval workflow assignee is invalid")
        try:
            assignee_type = ApprovalAssigneeType(raw_type)
            sequence = int(raw_sequence)
        except (TypeError, ValueError) as exc:
            raise SubcontractValidationError("Approval workflow assignee is invalid") from exc
        assignees.append(
            ApprovalAssignee(
                assignee_type=assignee_type,
                assignee_id=raw_id,
                sequence=sequence,
            )
        )
    return assignees


async def _workflow_instance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    definition_key: str,
    entity_type: str,
    entity_id: UUID,
) -> WorkflowInstance:
    instance = await db.scalar(
        select(WorkflowInstance)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowInstance.definition_id)
        .where(
            WorkflowInstance.organization_id == organization_id,
            WorkflowInstance.entity_type == entity_type,
            WorkflowInstance.entity_id == entity_id,
            WorkflowDefinition.key == definition_key,
        )
    )
    if instance is None:
        raise SubcontractValidationError("Approval workflow has not been started")
    return instance


async def _approval_transition(
    db: AsyncSession,
    *,
    instance: WorkflowInstance,
    transition_key: str,
) -> WorkflowTransition:
    transition = await db.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.organization_id == instance.organization_id,
            WorkflowTransition.workflow_version_id == instance.workflow_version_id,
            WorkflowTransition.key == transition_key,
            WorkflowTransition.from_state_key == instance.current_state_key,
            WorkflowTransition.active.is_(True),
        )
    )
    if transition is None:
        raise SubcontractValidationError("Approval transition is not available")
    return transition


async def _pending_request(
    db: AsyncSession,
    *,
    instance: WorkflowInstance,
    transition_key: str,
) -> WorkflowTransitionRequest:
    request = await db.scalar(
        select(WorkflowTransitionRequest).where(
            WorkflowTransitionRequest.organization_id == instance.organization_id,
            WorkflowTransitionRequest.workflow_instance_id == instance.id,
            WorkflowTransitionRequest.transition_key == transition_key,
            WorkflowTransitionRequest.status == TransitionRequestStatus.PENDING,
        )
    )
    if request is None:
        raise SubcontractValidationError("No pending approval request was found")
    return request


async def _pending_tasks(
    db: AsyncSession,
    *,
    organization_id: UUID,
    request_id: UUID,
) -> list[WorkflowApprovalTask]:
    return list(
        (
            await db.scalars(
                select(WorkflowApprovalTask)
                .where(
                    WorkflowApprovalTask.organization_id == organization_id,
                    WorkflowApprovalTask.transition_request_id == request_id,
                    WorkflowApprovalTask.status == ApprovalTaskStatus.PENDING,
                )
                .order_by(
                    WorkflowApprovalTask.sequence,
                    WorkflowApprovalTask.created_at,
                )
            )
        ).all()
    )


async def _eligible_assignees(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    permission_keys: set[str],
    pending_tasks: list[WorkflowApprovalTask],
) -> set[tuple[ApprovalAssigneeType, str]]:
    organization_role_keys = set(
        (
            await db.scalars(
                select(Role.key)
                .join(MembershipRole, MembershipRole.role_id == Role.id)
                .where(
                    MembershipRole.membership_id == membership_id,
                    Role.organization_id == organization_id,
                    Role.is_active.is_(True),
                )
            )
        ).all()
    )
    project_role_keys = set(
        (
            await db.scalars(
                select(Role.key)
                .join(ProjectRoleAssignment, ProjectRoleAssignment.role_id == Role.id)
                .join(
                    ProjectMembership,
                    ProjectMembership.id == ProjectRoleAssignment.project_membership_id,
                )
                .where(
                    ProjectMembership.organization_id == organization_id,
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.organization_membership_id == membership_id,
                    ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
                    ProjectRoleAssignment.organization_id == organization_id,
                    Role.organization_id == organization_id,
                    Role.is_active.is_(True),
                )
            )
        ).all()
    )
    eligible = {
        (ApprovalAssigneeType.ROLE, role_key) for role_key in organization_role_keys
    } | {
        (ApprovalAssigneeType.PROJECT_ROLE, role_key) for role_key in project_role_keys
    }
    eligible.add((ApprovalAssigneeType.USER, str(actor_user_id)))
    if "admin.workflow.manage" in permission_keys:
        eligible.update((task.assignee_type, task.assignee_id) for task in pending_tasks)
    return eligible


async def _decide_task(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    instance: WorkflowInstance,
    transition_key: str,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    approve: bool,
    reason: str | None,
    session_id: UUID | None,
) -> WorkflowTransitionRequest:
    request = await _pending_request(
        db,
        instance=instance,
        transition_key=transition_key,
    )
    tasks = await _pending_tasks(
        db,
        organization_id=organization_id,
        request_id=request.id,
    )
    eligible = await _eligible_assignees(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=actor_membership_id,
        actor_user_id=actor_user_id,
        permission_keys=permission_keys,
        pending_tasks=tasks,
    )
    task = next(
        (
            candidate
            for candidate in tasks
            if (candidate.assignee_type, candidate.assignee_id) in eligible
        ),
        None,
    )
    if task is None:
        raise SubcontractValidationError(
            "No pending approval task is assigned to the current user"
        )
    return await decide_approval_task(
        db,
        organization_id=organization_id,
        approval_task_id=task.id,
        actor_user_id=actor_user_id,
        eligible_assignees=eligible,
        approve=approve,
        comment=reason,
        session_id=session_id,
    )


async def submit_contract_for_approval(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subcontract_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Subcontract:
    try:
        await ensure_contract_approval_workflow(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        row = await transition_subcontract(
            db,
            organization_id=organization_id,
            project_id=project_id,
            subcontract_id=subcontract_id,
            expected_revision=expected_revision,
            target=SubcontractStatus.SUBMITTED,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            session_id=session_id,
            reason=reason,
        )
        instance = await start_workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=CONTRACT_WORKFLOW_KEY,
            entity_type=CONTRACT_ENTITY_TYPE,
            entity_id=subcontract_id,
            actor_user_id=actor_user_id,
        )
        instance = await execute_transition(
            db,
            workflow_instance_id=instance.id,
            organization_id=organization_id,
            transition_key="submit",
            expected_instance_version=instance.version,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            reason=reason,
            session_id=session_id,
            event_context={"project_id": str(project_id)},
        )
        transition = await _approval_transition(
            db,
            instance=instance,
            transition_key="approve",
        )
        await request_approval_transition(
            db,
            workflow_instance_id=instance.id,
            organization_id=organization_id,
            transition_key="approve",
            expected_instance_version=instance.version,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            approvers=_approval_assignees(transition.assignment_rule or {}),
            reason=reason,
            request_context={
                "project_id": str(project_id),
                "subcontract_id": str(subcontract_id),
            },
        )
        return row
    except WorkflowConflictError as exc:
        raise SubcontractConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise SubcontractValidationError(str(exc)) from exc


async def decide_contract_approval(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subcontract_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    approve: bool,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Subcontract:
    try:
        instance = await _workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=CONTRACT_WORKFLOW_KEY,
            entity_type=CONTRACT_ENTITY_TYPE,
            entity_id=subcontract_id,
        )
        request = await _decide_task(
            db,
            organization_id=organization_id,
            project_id=project_id,
            instance=instance,
            transition_key="approve",
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            approve=approve,
            reason=reason,
            session_id=session_id,
        )
        if approve and request.status == TransitionRequestStatus.APPROVED:
            await execute_approved_transition_request(
                db,
                organization_id=organization_id,
                transition_request_id=request.id,
                permission_keys=permission_keys,
                actor_user_id=actor_user_id,
                session_id=session_id,
                event_context={"project_id": str(project_id)},
            )
            return await transition_subcontract(
                db,
                organization_id=organization_id,
                project_id=project_id,
                subcontract_id=subcontract_id,
                expected_revision=expected_revision,
                target=SubcontractStatus.APPROVED,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                session_id=session_id,
                reason=reason,
            )

        if not approve:
            await execute_transition(
                db,
                workflow_instance_id=instance.id,
                organization_id=organization_id,
                transition_key="return_to_draft",
                expected_instance_version=instance.version,
                permission_keys=permission_keys,
                actor_user_id=actor_user_id,
                reason=reason,
                session_id=session_id,
                event_context={"project_id": str(project_id)},
            )
            return await transition_subcontract(
                db,
                organization_id=organization_id,
                project_id=project_id,
                subcontract_id=subcontract_id,
                expected_revision=expected_revision,
                target=SubcontractStatus.DRAFT,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                session_id=session_id,
                reason=reason,
            )

        row = await db.scalar(
            select(Subcontract).where(
                Subcontract.id == subcontract_id,
                Subcontract.organization_id == organization_id,
                Subcontract.project_id == project_id,
            )
        )
        if row is None:
            raise SubcontractValidationError("Work order was not found")
        return row
    except WorkflowConflictError as exc:
        raise SubcontractConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise SubcontractValidationError(str(exc)) from exc


async def submit_claim_for_certification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    try:
        await ensure_claim_certification_workflow(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        before = await db.scalar(
            select(SubcontractClaim).where(
                SubcontractClaim.id == claim_id,
                SubcontractClaim.organization_id == organization_id,
                SubcontractClaim.project_id == project_id,
            )
        )
        if before is None:
            raise SubcontractValidationError("Progress claim was not found")
        transition_key = (
            "resubmit"
            if before.status == SubcontractClaimStatus.REJECTED
            else "submit"
        )
        row = await submit_claim(
            db,
            organization_id=organization_id,
            project_id=project_id,
            claim_id=claim_id,
            expected_revision=expected_revision,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            session_id=session_id,
            reason=reason,
        )
        instance = await start_workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=CLAIM_WORKFLOW_KEY,
            entity_type=CLAIM_ENTITY_TYPE,
            entity_id=claim_id,
            actor_user_id=actor_user_id,
        )
        instance = await execute_transition(
            db,
            workflow_instance_id=instance.id,
            organization_id=organization_id,
            transition_key=transition_key,
            expected_instance_version=instance.version,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            reason=reason,
            session_id=session_id,
            event_context={"project_id": str(project_id)},
        )
        transition = await _approval_transition(
            db,
            instance=instance,
            transition_key="certify",
        )
        await request_approval_transition(
            db,
            workflow_instance_id=instance.id,
            organization_id=organization_id,
            transition_key="certify",
            expected_instance_version=instance.version,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            approvers=_approval_assignees(transition.assignment_rule or {}),
            reason=reason,
            request_context={
                "project_id": str(project_id),
                "claim_id": str(claim_id),
            },
        )
        return row
    except WorkflowConflictError as exc:
        raise SubcontractConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise SubcontractValidationError(str(exc)) from exc


async def decide_claim_certification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    approve: bool,
    other_deductions: Decimal = Decimal(0),
    tax_withheld_amount: Decimal = Decimal(0),
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    try:
        instance = await _workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=CLAIM_WORKFLOW_KEY,
            entity_type=CLAIM_ENTITY_TYPE,
            entity_id=claim_id,
        )
        request = await _decide_task(
            db,
            organization_id=organization_id,
            project_id=project_id,
            instance=instance,
            transition_key="certify",
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            actor_membership_id=actor_membership_id,
            approve=approve,
            reason=reason,
            session_id=session_id,
        )
        if approve and request.status == TransitionRequestStatus.APPROVED:
            await execute_approved_transition_request(
                db,
                organization_id=organization_id,
                transition_request_id=request.id,
                permission_keys=permission_keys,
                actor_user_id=actor_user_id,
                session_id=session_id,
                event_context={"project_id": str(project_id)},
            )
            return await certify_claim(
                db,
                organization_id=organization_id,
                project_id=project_id,
                claim_id=claim_id,
                expected_revision=expected_revision,
                other_deductions=other_deductions,
                tax_withheld_amount=tax_withheld_amount,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                session_id=session_id,
                reason=reason,
            )

        if not approve:
            await execute_transition(
                db,
                workflow_instance_id=instance.id,
                organization_id=organization_id,
                transition_key="reject",
                expected_instance_version=instance.version,
                permission_keys=permission_keys,
                actor_user_id=actor_user_id,
                reason=reason,
                session_id=session_id,
                event_context={"project_id": str(project_id)},
            )
            return await reject_claim(
                db,
                organization_id=organization_id,
                project_id=project_id,
                claim_id=claim_id,
                expected_revision=expected_revision,
                actor_user_id=actor_user_id,
                session_id=session_id,
                reason=reason,
            )

        row = await db.scalar(
            select(SubcontractClaim).where(
                SubcontractClaim.id == claim_id,
                SubcontractClaim.organization_id == organization_id,
                SubcontractClaim.project_id == project_id,
            )
        )
        if row is None:
            raise SubcontractValidationError("Progress claim was not found")
        return row
    except WorkflowConflictError as exc:
        raise SubcontractConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise SubcontractValidationError(str(exc)) from exc
