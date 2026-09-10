from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.workflows.models import (
    ApprovalAssigneeType,
    ApprovalTaskStatus,
    TransitionRequestStatus,
    WorkflowApprovalTask,
    WorkflowInstance,
    WorkflowTransitionRequest,
)
from app.modules.workflows.service import (
    WorkflowConflictError,
    WorkflowPermissionError,
    WorkflowValidationError,
    execute_transition,
)


async def decide_approval_task(
    db: AsyncSession,
    *,
    organization_id: UUID,
    approval_task_id: UUID,
    actor_user_id: UUID,
    eligible_assignees: set[tuple[ApprovalAssigneeType, str]],
    approve: bool,
    comment: str | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    now: datetime | None = None,
) -> WorkflowTransitionRequest:
    current = now or datetime.now(UTC)
    task = await db.scalar(
        select(WorkflowApprovalTask)
        .where(
            WorkflowApprovalTask.id == approval_task_id,
            WorkflowApprovalTask.organization_id == organization_id,
        )
        .with_for_update()
    )
    if task is None:
        raise WorkflowValidationError("Approval task was not found")
    if task.status != ApprovalTaskStatus.PENDING:
        raise WorkflowValidationError("Approval task has already been decided")
    if (task.assignee_type, task.assignee_id) not in eligible_assignees:
        raise WorkflowPermissionError("Current user is not eligible for this approval task")

    request = await db.scalar(
        select(WorkflowTransitionRequest)
        .where(
            WorkflowTransitionRequest.id == task.transition_request_id,
            WorkflowTransitionRequest.organization_id == organization_id,
        )
        .with_for_update()
    )
    if request is None or request.status != TransitionRequestStatus.PENDING:
        raise WorkflowValidationError("Approval request is no longer pending")

    tasks = list(
        (
            await db.scalars(
                select(WorkflowApprovalTask)
                .where(
                    WorkflowApprovalTask.organization_id == organization_id,
                    WorkflowApprovalTask.transition_request_id == request.id,
                )
                .order_by(WorkflowApprovalTask.sequence, WorkflowApprovalTask.created_at)
                .with_for_update()
            )
        ).all()
    )
    earlier = [candidate for candidate in tasks if candidate.sequence < task.sequence]
    if any(candidate.status != ApprovalTaskStatus.APPROVED for candidate in earlier):
        raise WorkflowValidationError("Earlier approval sequence must be completed first")

    task.status = ApprovalTaskStatus.APPROVED if approve else ApprovalTaskStatus.REJECTED
    task.decided_by_user_id = actor_user_id
    task.decided_at = current
    task.comment = comment.strip() if comment else None

    if not approve:
        request.status = TransitionRequestStatus.REJECTED
        request.resolved_at = current
        for candidate in tasks:
            if candidate.id != task.id and candidate.status == ApprovalTaskStatus.PENDING:
                candidate.status = ApprovalTaskStatus.CANCELLED
    elif all(
        candidate.status == ApprovalTaskStatus.APPROVED
        for candidate in tasks
        if candidate.id != task.id
    ):
        request.status = TransitionRequestStatus.APPROVED
        request.resolved_at = current

    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workflow.approval.decided",
        target_type="workflow_transition_request",
        target_id=str(request.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.HIGH,
        changes={
            "approval_task_id": task.id,
            "decision": task.status.value,
            "request_status": request.status.value,
            "sequence": task.sequence,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workflow.approval.changed",
        entity_type="workflow_transition_request",
        entity_id=request.id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={
            "approval_task_id": task.id,
            "request_status": request.status.value,
        },
    )
    return request


async def cancel_transition_request(
    db: AsyncSession,
    *,
    organization_id: UUID,
    transition_request_id: UUID,
    actor_user_id: UUID,
    reason: str | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    now: datetime | None = None,
) -> WorkflowTransitionRequest:
    current = now or datetime.now(UTC)
    request = await db.scalar(
        select(WorkflowTransitionRequest)
        .where(
            WorkflowTransitionRequest.id == transition_request_id,
            WorkflowTransitionRequest.organization_id == organization_id,
        )
        .with_for_update()
    )
    if request is None:
        raise WorkflowValidationError("Transition request was not found")
    if request.status != TransitionRequestStatus.PENDING:
        raise WorkflowValidationError("Only pending transition requests can be cancelled")
    if request.requested_by_user_id != actor_user_id:
        raise WorkflowPermissionError("Only the requester can cancel this transition request")

    request.status = TransitionRequestStatus.CANCELLED
    request.resolved_at = current
    tasks = list(
        (
            await db.scalars(
                select(WorkflowApprovalTask).where(
                    WorkflowApprovalTask.organization_id == organization_id,
                    WorkflowApprovalTask.transition_request_id == request.id,
                    WorkflowApprovalTask.status == ApprovalTaskStatus.PENDING,
                )
            )
        ).all()
    )
    for task in tasks:
        task.status = ApprovalTaskStatus.CANCELLED

    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workflow.approval.cancelled",
        target_type="workflow_transition_request",
        target_id=str(request.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
    )
    return request


async def execute_approved_transition_request(
    db: AsyncSession,
    *,
    organization_id: UUID,
    transition_request_id: UUID,
    permission_keys: set[str],
    actor_user_id: UUID,
    step_up_satisfied: bool = False,
    conditions_satisfied: bool | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    event_context: dict[str, object] | None = None,
    now: datetime | None = None,
) -> WorkflowInstance:
    request = await db.scalar(
        select(WorkflowTransitionRequest)
        .where(
            WorkflowTransitionRequest.id == transition_request_id,
            WorkflowTransitionRequest.organization_id == organization_id,
        )
        .with_for_update()
    )
    if request is None:
        raise WorkflowValidationError("Transition request was not found")
    if request.status != TransitionRequestStatus.APPROVED:
        raise WorkflowValidationError("Transition request has not been fully approved")

    instance = await db.scalar(
        select(WorkflowInstance)
        .where(
            WorkflowInstance.id == request.workflow_instance_id,
            WorkflowInstance.organization_id == organization_id,
        )
        .with_for_update()
    )
    if instance is None:
        raise WorkflowValidationError("Workflow instance was not found")
    if instance.version != request.expected_instance_version:
        raise WorkflowConflictError(
            "Workflow changed after approval was requested; approval must be reviewed again"
        )
    if instance.current_state_key != request.from_state_key:
        raise WorkflowConflictError("Workflow state changed after approval was requested")

    transitioned = await execute_transition(
        db,
        workflow_instance_id=instance.id,
        organization_id=organization_id,
        transition_key=request.transition_key,
        expected_instance_version=request.expected_instance_version,
        permission_keys=permission_keys,
        actor_user_id=actor_user_id,
        reason=request.reason,
        step_up_satisfied=step_up_satisfied,
        conditions_satisfied=conditions_satisfied,
        approval_completed=True,
        session_id=session_id,
        correlation_id=correlation_id,
        event_context=event_context,
        now=now,
    )
    request.status = TransitionRequestStatus.EXECUTED
    request.resolved_at = now or datetime.now(UTC)
    await db.flush()
    return transitioned
