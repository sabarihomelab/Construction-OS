from dataclasses import dataclass
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
    WorkflowDefinition,
    WorkflowHistoryEvent,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowState,
    WorkflowStateKind,
    WorkflowTransition,
    WorkflowTransitionRequest,
    WorkflowVersion,
    WorkflowVersionStatus,
)


class WorkflowValidationError(ValueError):
    pass


class WorkflowConflictError(WorkflowValidationError):
    pass


class WorkflowPermissionError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ApprovalAssignee:
    assignee_type: ApprovalAssigneeType
    assignee_id: str
    sequence: int = 1
    due_at: datetime | None = None


async def validate_workflow_version(db: AsyncSession, workflow_version: WorkflowVersion) -> None:
    states = list(
        (
            await db.scalars(
                select(WorkflowState).where(
                    WorkflowState.organization_id == workflow_version.organization_id,
                    WorkflowState.workflow_version_id == workflow_version.id,
                )
            )
        ).all()
    )
    if not states:
        raise WorkflowValidationError("Workflow version must contain at least one state")

    initial_states = [state for state in states if state.kind == WorkflowStateKind.INITIAL]
    if len(initial_states) != 1:
        raise WorkflowValidationError("Workflow version must contain exactly one initial state")

    state_keys = {state.key for state in states}
    transitions = list(
        (
            await db.scalars(
                select(WorkflowTransition).where(
                    WorkflowTransition.organization_id == workflow_version.organization_id,
                    WorkflowTransition.workflow_version_id == workflow_version.id,
                    WorkflowTransition.active.is_(True),
                )
            )
        ).all()
    )
    for transition in transitions:
        if transition.from_state_key not in state_keys or transition.to_state_key not in state_keys:
            raise WorkflowValidationError(
                f"Transition {transition.key} references a state outside this workflow version"
            )

    terminal_keys = {
        state.key
        for state in states
        if state.kind in (WorkflowStateKind.COMPLETED, WorkflowStateKind.CANCELLED)
    }
    for transition in transitions:
        if transition.from_state_key in terminal_keys:
            raise WorkflowValidationError(
                f"Terminal state {transition.from_state_key} cannot have outgoing transitions"
            )


async def publish_workflow_version(
    db: AsyncSession,
    *,
    workflow_version_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    effective_from: datetime | None = None,
    now: datetime | None = None,
) -> WorkflowVersion:
    current = now or datetime.now(UTC)
    workflow_version = await db.scalar(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.id == workflow_version_id,
            WorkflowVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if workflow_version is None:
        raise WorkflowValidationError("Workflow version was not found")
    if workflow_version.status != WorkflowVersionStatus.DRAFT:
        raise WorkflowValidationError("Only draft workflow versions can be published")

    await validate_workflow_version(db, workflow_version)
    definition = await db.scalar(
        select(WorkflowDefinition)
        .where(
            WorkflowDefinition.id == workflow_version.definition_id,
            WorkflowDefinition.organization_id == organization_id,
        )
        .with_for_update()
    )
    if definition is None or not definition.active:
        raise WorkflowValidationError("Active workflow definition was not found")

    active_versions = list(
        (
            await db.scalars(
                select(WorkflowVersion).where(
                    WorkflowVersion.definition_id == definition.id,
                    WorkflowVersion.organization_id == organization_id,
                    WorkflowVersion.status == WorkflowVersionStatus.ACTIVE,
                )
            )
        ).all()
    )
    for active_version in active_versions:
        active_version.status = WorkflowVersionStatus.RETIRED

    workflow_version.status = WorkflowVersionStatus.ACTIVE
    workflow_version.effective_from = effective_from or current
    workflow_version.published_at = current
    workflow_version.published_by_user_id = actor_user_id
    definition.current_version = workflow_version.version
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workflow.version.published",
        target_type="workflow_definition",
        target_id=str(definition.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.HIGH,
        changes={"published_version": workflow_version.version},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workflow.definition.changed",
        entity_type="workflow_definition",
        entity_id=definition.id,
        entity_version=workflow_version.version,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"workflow_key": definition.key, "version": workflow_version.version},
    )
    return workflow_version


async def start_workflow_instance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    definition_key: str,
    entity_type: str,
    entity_id: UUID,
    actor_user_id: UUID | None,
    correlation_id: UUID | None = None,
) -> WorkflowInstance:
    definition = await db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.organization_id == organization_id,
            WorkflowDefinition.key == definition_key,
            WorkflowDefinition.entity_type == entity_type,
            WorkflowDefinition.active.is_(True),
        )
    )
    if definition is None or definition.current_version < 1:
        raise WorkflowValidationError("Published workflow definition was not found")

    workflow_version = await db.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.organization_id == organization_id,
            WorkflowVersion.definition_id == definition.id,
            WorkflowVersion.version == definition.current_version,
            WorkflowVersion.status == WorkflowVersionStatus.ACTIVE,
        )
    )
    if workflow_version is None:
        raise WorkflowValidationError("Active workflow version was not found")

    initial_state = await db.scalar(
        select(WorkflowState).where(
            WorkflowState.organization_id == organization_id,
            WorkflowState.workflow_version_id == workflow_version.id,
            WorkflowState.kind == WorkflowStateKind.INITIAL,
        )
    )
    if initial_state is None:
        raise WorkflowValidationError("Workflow has no initial state")

    existing = await db.scalar(
        select(WorkflowInstance).where(
            WorkflowInstance.organization_id == organization_id,
            WorkflowInstance.definition_id == definition.id,
            WorkflowInstance.entity_type == entity_type,
            WorkflowInstance.entity_id == entity_id,
        )
    )
    if existing is not None:
        return existing

    instance = WorkflowInstance(
        organization_id=organization_id,
        definition_id=definition.id,
        workflow_version_id=workflow_version.id,
        entity_type=entity_type,
        entity_id=entity_id,
        current_state_key=initial_state.key,
        status=WorkflowInstanceStatus.ACTIVE,
        version=1,
        started_by_user_id=actor_user_id,
    )
    db.add(instance)
    await db.flush()
    return instance


async def _load_transition(
    db: AsyncSession,
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
        raise WorkflowValidationError("Transition is not available from the current state")
    return transition


def _validate_transition_access(
    transition: WorkflowTransition,
    *,
    permission_keys: set[str],
    reason: str | None,
    step_up_satisfied: bool,
    conditions_satisfied: bool | None,
    approval_completed: bool,
) -> None:
    if transition.required_permission_key and transition.required_permission_key not in permission_keys:
        raise WorkflowPermissionError("Required transition permission is not granted")
    if transition.requires_reason and not (reason and reason.strip()):
        raise WorkflowValidationError("A reason is required for this transition")
    if transition.requires_step_up_mfa and not step_up_satisfied:
        raise WorkflowPermissionError("Step-up authentication is required for this transition")
    if transition.conditions and conditions_satisfied is not True:
        raise WorkflowValidationError("Domain transition conditions have not been satisfied")
    if transition.approval_policy and not approval_completed:
        raise WorkflowValidationError("This transition requires approval before execution")


async def execute_transition(
    db: AsyncSession,
    *,
    workflow_instance_id: UUID,
    organization_id: UUID,
    transition_key: str,
    expected_instance_version: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    reason: str | None = None,
    step_up_satisfied: bool = False,
    conditions_satisfied: bool | None = None,
    approval_completed: bool = False,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    event_context: dict[str, object] | None = None,
    now: datetime | None = None,
) -> WorkflowInstance:
    current = now or datetime.now(UTC)
    instance = await db.scalar(
        select(WorkflowInstance)
        .where(
            WorkflowInstance.id == workflow_instance_id,
            WorkflowInstance.organization_id == organization_id,
        )
        .with_for_update()
    )
    if instance is None:
        raise WorkflowValidationError("Workflow instance was not found")
    if instance.status != WorkflowInstanceStatus.ACTIVE:
        raise WorkflowValidationError("Workflow instance is no longer active")
    if instance.version != expected_instance_version:
        raise WorkflowConflictError(
            f"Workflow changed from version {expected_instance_version} to {instance.version}"
        )

    transition = await _load_transition(db, instance, transition_key)
    _validate_transition_access(
        transition,
        permission_keys=permission_keys,
        reason=reason,
        step_up_satisfied=step_up_satisfied,
        conditions_satisfied=conditions_satisfied,
        approval_completed=approval_completed,
    )
    target_state = await db.scalar(
        select(WorkflowState).where(
            WorkflowState.organization_id == organization_id,
            WorkflowState.workflow_version_id == instance.workflow_version_id,
            WorkflowState.key == transition.to_state_key,
        )
    )
    if target_state is None:
        raise WorkflowValidationError("Transition target state was not found")

    from_state = instance.current_state_key
    instance.current_state_key = target_state.key
    instance.version += 1
    if target_state.kind == WorkflowStateKind.COMPLETED:
        instance.status = WorkflowInstanceStatus.COMPLETED
        instance.completed_at = current
    elif target_state.kind == WorkflowStateKind.CANCELLED:
        instance.status = WorkflowInstanceStatus.CANCELLED
        instance.completed_at = current

    history = WorkflowHistoryEvent(
        organization_id=organization_id,
        workflow_instance_id=instance.id,
        instance_version=instance.version,
        transition_key=transition.key,
        from_state_key=from_state,
        to_state_key=target_state.key,
        actor_user_id=actor_user_id,
        reason=reason.strip() if reason else None,
        occurred_at=current,
        correlation_id=correlation_id,
        event_context=event_context or {},
    )
    db.add(history)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workflow.transition.executed",
        target_type=instance.entity_type,
        target_id=str(instance.entity_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "workflow_instance_id": instance.id,
            "from_state": from_state,
            "to_state": target_state.key,
            "transition": transition.key,
            "instance_version": instance.version,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="workflow.instance.changed",
        entity_type=instance.entity_type,
        entity_id=instance.entity_id,
        entity_version=instance.version,
        required_permission_key=transition.required_permission_key,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={
            "workflow_instance_id": instance.id,
            "state": target_state.key,
            "transition": transition.key,
        },
    )
    return instance


async def request_approval_transition(
    db: AsyncSession,
    *,
    workflow_instance_id: UUID,
    organization_id: UUID,
    transition_key: str,
    expected_instance_version: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    approvers: list[ApprovalAssignee],
    reason: str | None = None,
    step_up_satisfied: bool = False,
    conditions_satisfied: bool | None = None,
    request_context: dict[str, object] | None = None,
) -> WorkflowTransitionRequest:
    if not approvers:
        raise WorkflowValidationError("At least one approval assignee is required")

    instance = await db.scalar(
        select(WorkflowInstance)
        .where(
            WorkflowInstance.id == workflow_instance_id,
            WorkflowInstance.organization_id == organization_id,
        )
        .with_for_update()
    )
    if instance is None or instance.status != WorkflowInstanceStatus.ACTIVE:
        raise WorkflowValidationError("Active workflow instance was not found")
    if instance.version != expected_instance_version:
        raise WorkflowConflictError(
            f"Workflow changed from version {expected_instance_version} to {instance.version}"
        )

    transition = await _load_transition(db, instance, transition_key)
    if not transition.approval_policy:
        raise WorkflowValidationError("This transition does not require an approval request")
    _validate_transition_access(
        transition,
        permission_keys=permission_keys,
        reason=reason,
        step_up_satisfied=step_up_satisfied,
        conditions_satisfied=conditions_satisfied,
        approval_completed=True,
    )

    pending = await db.scalar(
        select(WorkflowTransitionRequest).where(
            WorkflowTransitionRequest.organization_id == organization_id,
            WorkflowTransitionRequest.workflow_instance_id == instance.id,
            WorkflowTransitionRequest.status == TransitionRequestStatus.PENDING,
        )
    )
    if pending is not None:
        return pending

    request = WorkflowTransitionRequest(
        organization_id=organization_id,
        workflow_instance_id=instance.id,
        transition_key=transition.key,
        from_state_key=instance.current_state_key,
        to_state_key=transition.to_state_key,
        expected_instance_version=instance.version,
        status=TransitionRequestStatus.PENDING,
        requested_by_user_id=actor_user_id,
        reason=reason.strip() if reason else None,
        request_context=request_context or {},
    )
    db.add(request)
    await db.flush()

    for approver in approvers:
        if approver.sequence < 1 or not approver.assignee_id.strip():
            raise WorkflowValidationError("Approval assignee and sequence must be valid")
        db.add(
            WorkflowApprovalTask(
                organization_id=organization_id,
                transition_request_id=request.id,
                sequence=approver.sequence,
                assignee_type=approver.assignee_type,
                assignee_id=approver.assignee_id.strip(),
                status=ApprovalTaskStatus.PENDING,
                due_at=approver.due_at,
            )
        )
    await db.flush()
    return request
