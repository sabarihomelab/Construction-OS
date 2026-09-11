from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.workflows.models import (
    ApprovalTaskStatus,
    TransitionRequestStatus,
    WorkflowApprovalTask,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowState,
    WorkflowStateKind,
    WorkflowTransitionRequest,
)
from app.modules.workforce.attendance_models import (
    AttendanceHistoryType,
    AttendanceRegister,
    AttendanceRegisterStatus,
)
from app.modules.workforce.attendance_service import (
    _history,
    _load_register_for_update,
    _publish,
)
from app.modules.workforce.service import WorkforceValidationError


async def reopen_attendance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    register_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str,
) -> AttendanceRegister:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise WorkforceValidationError("A reason is required to reopen attendance")

    register = await _load_register_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        register_id=register_id,
        expected_revision=expected_revision,
    )
    if register.status not in {
        AttendanceRegisterStatus.SUBMITTED,
        AttendanceRegisterStatus.IN_REVIEW,
        AttendanceRegisterStatus.APPROVED,
    }:
        raise WorkforceValidationError(
            "Only submitted, in-review, or approved attendance can be reopened"
        )

    previous_status = register.status
    now = datetime.now(UTC)
    if register.workflow_instance_id is not None:
        workflow = await db.scalar(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.id == register.workflow_instance_id,
                WorkflowInstance.organization_id == organization_id,
            )
            .with_for_update()
        )
        if workflow is None:
            raise WorkforceValidationError("Attendance workflow instance was not found")

        initial_state = await db.scalar(
            select(WorkflowState)
            .where(
                WorkflowState.organization_id == organization_id,
                WorkflowState.workflow_version_id == workflow.workflow_version_id,
                WorkflowState.kind == WorkflowStateKind.INITIAL,
            )
            .order_by(WorkflowState.display_order, WorkflowState.id)
        )
        if initial_state is None:
            raise WorkforceValidationError("Attendance workflow has no initial state")

        pending_request_ids = list(
            (
                await db.scalars(
                    select(WorkflowTransitionRequest.id).where(
                        WorkflowTransitionRequest.organization_id == organization_id,
                        WorkflowTransitionRequest.workflow_instance_id == workflow.id,
                        WorkflowTransitionRequest.status == TransitionRequestStatus.PENDING,
                    )
                )
            ).all()
        )
        if pending_request_ids:
            await db.execute(
                update(WorkflowApprovalTask)
                .where(
                    WorkflowApprovalTask.organization_id == organization_id,
                    WorkflowApprovalTask.transition_request_id.in_(pending_request_ids),
                    WorkflowApprovalTask.status == ApprovalTaskStatus.PENDING,
                )
                .values(status=ApprovalTaskStatus.CANCELLED)
            )
            await db.execute(
                update(WorkflowTransitionRequest)
                .where(
                    WorkflowTransitionRequest.organization_id == organization_id,
                    WorkflowTransitionRequest.id.in_(pending_request_ids),
                )
                .values(
                    status=TransitionRequestStatus.CANCELLED,
                    resolved_at=now,
                )
            )

        workflow.current_state_key = initial_state.key
        workflow.status = WorkflowInstanceStatus.ACTIVE
        workflow.completed_at = None
        workflow.version += 1

    register.status = AttendanceRegisterStatus.DRAFT
    register.submitted_at = None
    register.approved_at = None
    register.approved_by_membership_id = None
    register.rejected_at = None
    register.revision += 1
    await db.flush()

    await _history(
        db,
        register=register,
        event_type=AttendanceHistoryType.REOPENED,
        actor_user_id=actor_user_id,
        details={
            "from_status": previous_status.value,
            "reason": normalized_reason,
        },
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="workforce.attendance.reopened",
        target_type="attendance_register",
        target_id=str(register.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=normalized_reason,
        changes={
            "from_status": previous_status.value,
            "status": register.status.value,
            "revision": register.revision,
        },
    )
    await _publish(
        db,
        register=register,
        event_type="workforce.attendance.reopened",
        actor_user_id=actor_user_id,
        session_id=session_id,
        extra={"from_status": previous_status.value},
    )
    return register
