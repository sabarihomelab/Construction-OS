from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.models import MembershipRole, Role
from app.modules.financials.payables_models import VendorBill, VendorBillStatus
from app.modules.financials.payables_service import (
    VendorPayableConflictError,
    VendorPayableValidationError,
    approve_vendor_bill,
    reject_vendor_bill,
    submit_vendor_bill,
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

VENDOR_BILL_WORKFLOW_KEY = "financials.vendor_bill.approval"
VENDOR_BILL_ENTITY_TYPE = "vendor_bill"
DEFAULT_APPROVER_ROLE_KEY = "company-management"


async def ensure_vendor_bill_approval_workflow(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WorkflowDefinition:
    definition = await db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.organization_id == organization_id,
            WorkflowDefinition.key == VENDOR_BILL_WORKFLOW_KEY,
        )
    )
    if definition is not None:
        if not definition.active or definition.current_version < 1:
            raise VendorPayableValidationError(
                "Vendor bill approval workflow exists but is not published"
            )
        return definition

    definition = WorkflowDefinition(
        organization_id=organization_id,
        key=VENDOR_BILL_WORKFLOW_KEY,
        entity_type=VENDOR_BILL_ENTITY_TYPE,
        name="Vendor Bill Approval",
        description="Default India-first vendor bill approval workflow.",
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

    for order, (key, label, kind) in enumerate(
        [
            ("draft", "Draft", WorkflowStateKind.INITIAL),
            ("submitted", "Submitted", WorkflowStateKind.ACTIVE),
            ("rejected", "Rejected", WorkflowStateKind.ACTIVE),
            ("approved", "Approved", WorkflowStateKind.COMPLETED),
        ],
        start=1,
    ):
        db.add(
            WorkflowState(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key=key,
                label=label,
                kind=kind,
                display_order=order * 10,
            )
        )

    assignment_rule = {
        "assignees": [
            {
                "assignee_type": ApprovalAssigneeType.ROLE.value,
                "assignee_id": DEFAULT_APPROVER_ROLE_KEY,
                "sequence": 1,
            }
        ]
    }
    db.add_all(
        [
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="submit",
                name="Submit vendor bill",
                from_state_key="draft",
                to_state_key="submitted",
                required_permission_key="financials.payable.submit",
            ),
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="resubmit",
                name="Resubmit vendor bill",
                from_state_key="rejected",
                to_state_key="submitted",
                required_permission_key="financials.payable.submit",
            ),
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="approve",
                name="Approve vendor bill",
                from_state_key="submitted",
                to_state_key="approved",
                approval_policy={"mode": "sequential"},
                assignment_rule=assignment_rule,
            ),
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="reject",
                name="Reject vendor bill",
                from_state_key="submitted",
                to_state_key="rejected",
                required_permission_key="financials.payable.approve",
                requires_reason=True,
            ),
        ]
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


def _approval_assignees(assignment_rule: Mapping[str, object]) -> list[ApprovalAssignee]:
    raw = assignment_rule.get("assignees")
    if not isinstance(raw, list) or not raw:
        raise VendorPayableValidationError("Approval workflow has no configured assignee")

    result: list[ApprovalAssignee] = []
    for item in raw:
        if not isinstance(item, dict):
            raise VendorPayableValidationError("Approval workflow assignee is invalid")
        raw_type = item.get("assignee_type")
        raw_id = item.get("assignee_id")
        if not isinstance(raw_type, str) or not isinstance(raw_id, str):
            raise VendorPayableValidationError("Approval workflow assignee is invalid")
        try:
            result.append(
                ApprovalAssignee(
                    assignee_type=ApprovalAssigneeType(raw_type),
                    assignee_id=raw_id,
                    sequence=int(item.get("sequence", 1)),
                )
            )
        except (TypeError, ValueError) as exc:
            raise VendorPayableValidationError(
                "Approval workflow assignee is invalid"
            ) from exc
    return result


async def _instance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    vendor_bill_id: UUID,
) -> WorkflowInstance:
    instance = await db.scalar(
        select(WorkflowInstance)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowInstance.definition_id)
        .where(
            WorkflowInstance.organization_id == organization_id,
            WorkflowInstance.entity_type == VENDOR_BILL_ENTITY_TYPE,
            WorkflowInstance.entity_id == vendor_bill_id,
            WorkflowDefinition.key == VENDOR_BILL_WORKFLOW_KEY,
        )
    )
    if instance is None:
        raise VendorPayableValidationError("Vendor bill approval workflow has not been started")
    return instance


async def _approval_transition(
    db: AsyncSession,
    *,
    instance: WorkflowInstance,
) -> WorkflowTransition:
    transition = await db.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.organization_id == instance.organization_id,
            WorkflowTransition.workflow_version_id == instance.workflow_version_id,
            WorkflowTransition.key == "approve",
            WorkflowTransition.from_state_key == instance.current_state_key,
            WorkflowTransition.active.is_(True),
        )
    )
    if transition is None:
        raise VendorPayableValidationError("Vendor bill approval transition is not available")
    return transition


async def _pending_request(
    db: AsyncSession,
    *,
    instance: WorkflowInstance,
) -> WorkflowTransitionRequest:
    request = await db.scalar(
        select(WorkflowTransitionRequest).where(
            WorkflowTransitionRequest.organization_id == instance.organization_id,
            WorkflowTransitionRequest.workflow_instance_id == instance.id,
            WorkflowTransitionRequest.transition_key == "approve",
            WorkflowTransitionRequest.status == TransitionRequestStatus.PENDING,
        )
    )
    if request is None:
        raise VendorPayableValidationError("No pending vendor bill approval was found")
    return request


async def _eligible_assignees(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    permission_keys: set[str],
    pending_tasks: list[WorkflowApprovalTask],
) -> set[tuple[ApprovalAssigneeType, str]]:
    role_keys = set(
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
    eligible = {(ApprovalAssigneeType.ROLE, key) for key in role_keys}
    eligible.add((ApprovalAssigneeType.USER, str(actor_user_id)))
    if "admin.workflow.manage" in permission_keys:
        eligible.update((task.assignee_type, task.assignee_id) for task in pending_tasks)
    return eligible


async def submit_vendor_bill_for_approval(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    allow_variance_override: bool,
    permission_keys: set[str],
    actor_user_id: UUID,
    reason: str | None,
    session_id: UUID | None = None,
) -> VendorBill:
    try:
        await ensure_vendor_bill_approval_workflow(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        before = await db.scalar(
            select(VendorBill).where(
                VendorBill.id == vendor_bill_id,
                VendorBill.organization_id == organization_id,
                VendorBill.project_id == project_id,
            )
        )
        if before is None:
            raise VendorPayableValidationError("Vendor bill was not found")
        transition_key = "resubmit" if before.status == VendorBillStatus.REJECTED else "submit"
        bill = await submit_vendor_bill(
            db,
            organization_id=organization_id,
            project_id=project_id,
            vendor_bill_id=vendor_bill_id,
            membership_id=membership_id,
            expected_revision=expected_revision,
            allow_variance_override=allow_variance_override,
            reason=reason,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        instance = await start_workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=VENDOR_BILL_WORKFLOW_KEY,
            entity_type=VENDOR_BILL_ENTITY_TYPE,
            entity_id=vendor_bill_id,
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
        transition = await _approval_transition(db, instance=instance)
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
                "vendor_bill_id": str(vendor_bill_id),
            },
        )
        return bill
    except WorkflowConflictError as exc:
        raise VendorPayableConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise VendorPayableValidationError(str(exc)) from exc


async def decide_vendor_bill_approval(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    approve: bool,
    reason: str | None,
    session_id: UUID | None = None,
) -> VendorBill:
    try:
        instance = await _instance(
            db,
            organization_id=organization_id,
            vendor_bill_id=vendor_bill_id,
        )
        request = await _pending_request(db, instance=instance)
        tasks = list(
            (
                await db.scalars(
                    select(WorkflowApprovalTask)
                    .where(
                        WorkflowApprovalTask.organization_id == organization_id,
                        WorkflowApprovalTask.transition_request_id == request.id,
                        WorkflowApprovalTask.status == ApprovalTaskStatus.PENDING,
                    )
                    .order_by(
                        WorkflowApprovalTask.sequence,
                        WorkflowApprovalTask.created_at,
                    )
                )
            ).all()
        )
        eligible = await _eligible_assignees(
            db,
            organization_id=organization_id,
            membership_id=membership_id,
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
            raise VendorPayableValidationError(
                "No pending approval task is assigned to the current user"
            )

        request = await decide_approval_task(
            db,
            organization_id=organization_id,
            approval_task_id=task.id,
            actor_user_id=actor_user_id,
            eligible_assignees=eligible,
            approve=approve,
            comment=reason,
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
            return await approve_vendor_bill(
                db,
                organization_id=organization_id,
                project_id=project_id,
                vendor_bill_id=vendor_bill_id,
                membership_id=membership_id,
                expected_revision=expected_revision,
                reason=reason,
                actor_user_id=actor_user_id,
                session_id=session_id,
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
            return await reject_vendor_bill(
                db,
                organization_id=organization_id,
                project_id=project_id,
                vendor_bill_id=vendor_bill_id,
                membership_id=membership_id,
                expected_revision=expected_revision,
                reason=reason,
                actor_user_id=actor_user_id,
                session_id=session_id,
            )

        bill = await db.scalar(
            select(VendorBill).where(
                VendorBill.id == vendor_bill_id,
                VendorBill.organization_id == organization_id,
                VendorBill.project_id == project_id,
            )
        )
        if bill is None:
            raise VendorPayableValidationError("Vendor bill was not found")
        return bill
    except WorkflowConflictError as exc:
        raise VendorPayableConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise VendorPayableValidationError(str(exc)) from exc
