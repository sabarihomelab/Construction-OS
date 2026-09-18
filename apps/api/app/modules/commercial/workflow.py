from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.models import MembershipRole, Role
from app.modules.commercial.models import (
    MeasurementEntry,
    MeasurementStatus,
    RABill,
    RABillStatus,
)
from app.modules.commercial.service import (
    CommercialConflictError,
    CommercialValidationError,
    transition_measurement,
    transition_ra_bill,
)
from app.modules.projects.models import (
    ProjectMembership,
    ProjectMembershipStatus,
    ProjectRoleAssignment,
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

MEASUREMENT_WORKFLOW_KEY = "commercial.measurement.certification"
MEASUREMENT_ENTITY_TYPE = "measurement_entry"
RA_BILL_WORKFLOW_KEY = "commercial.ra_bill.certification"
RA_BILL_ENTITY_TYPE = "ra_bill"
DEFAULT_APPROVER_ROLE_KEY = "project-manager"


async def _ensure_definition(
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
            raise CommercialValidationError(f"{name} workflow exists but is not published")
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


async def ensure_measurement_certification_workflow(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WorkflowDefinition:
    return await _ensure_definition(
        db,
        organization_id=organization_id,
        key=MEASUREMENT_WORKFLOW_KEY,
        entity_type=MEASUREMENT_ENTITY_TYPE,
        name="Measurement Certification",
        states=[
            ("draft", "Draft", WorkflowStateKind.INITIAL),
            ("submitted", "Submitted", WorkflowStateKind.ACTIVE),
            ("rejected", "Rejected", WorkflowStateKind.ACTIVE),
            ("certified", "Certified", WorkflowStateKind.COMPLETED),
        ],
        transitions=[
            {
                "key": "submit",
                "name": "Submit measurement",
                "from_state_key": "draft",
                "to_state_key": "submitted",
                "required_permission_key": "commercial.measurement.submit",
            },
            {
                "key": "resubmit",
                "name": "Resubmit measurement",
                "from_state_key": "rejected",
                "to_state_key": "submitted",
                "required_permission_key": "commercial.measurement.submit",
            },
            {
                "key": "certify",
                "name": "Certify measurement",
                "from_state_key": "submitted",
                "to_state_key": "certified",
                "approval_policy": {"mode": "sequential"},
                "assignment_rule": _default_assignment_rule(),
            },
            {
                "key": "reject",
                "name": "Reject measurement",
                "from_state_key": "submitted",
                "to_state_key": "rejected",
                "required_permission_key": "commercial.measurement.certify",
                "requires_reason": True,
            },
        ],
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def ensure_ra_bill_certification_workflow(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WorkflowDefinition:
    return await _ensure_definition(
        db,
        organization_id=organization_id,
        key=RA_BILL_WORKFLOW_KEY,
        entity_type=RA_BILL_ENTITY_TYPE,
        name="Client RA Bill Certification",
        states=[
            ("draft", "Draft", WorkflowStateKind.INITIAL),
            ("submitted", "Submitted", WorkflowStateKind.ACTIVE),
            ("certified", "Certified", WorkflowStateKind.COMPLETED),
        ],
        transitions=[
            {
                "key": "submit",
                "name": "Submit RA bill",
                "from_state_key": "draft",
                "to_state_key": "submitted",
                "required_permission_key": "commercial.ra_bill.submit",
            },
            {
                "key": "certify",
                "name": "Certify RA bill",
                "from_state_key": "submitted",
                "to_state_key": "certified",
                "approval_policy": {"mode": "sequential"},
                "assignment_rule": _default_assignment_rule(),
            },
            {
                "key": "return_to_draft",
                "name": "Return RA bill to draft",
                "from_state_key": "submitted",
                "to_state_key": "draft",
                "required_permission_key": "commercial.ra_bill.certify",
                "requires_reason": True,
            },
        ],
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


def _approval_assignees(assignment_rule: Mapping[str, object]) -> list[ApprovalAssignee]:
    raw_assignees = assignment_rule.get("assignees")
    if not isinstance(raw_assignees, list) or not raw_assignees:
        raise CommercialValidationError("Approval workflow has no configured assignee")

    result: list[ApprovalAssignee] = []
    for raw in raw_assignees:
        if not isinstance(raw, dict):
            raise CommercialValidationError("Approval workflow assignee is invalid")
        raw_type = raw.get("assignee_type")
        raw_id = raw.get("assignee_id")
        raw_sequence = raw.get("sequence", 1)
        if not isinstance(raw_type, str) or not isinstance(raw_id, str):
            raise CommercialValidationError("Approval workflow assignee is invalid")
        try:
            assignee_type = ApprovalAssigneeType(raw_type)
            sequence = int(raw_sequence)
        except (TypeError, ValueError) as exc:
            raise CommercialValidationError("Approval workflow assignee is invalid") from exc
        result.append(
            ApprovalAssignee(
                assignee_type=assignee_type,
                assignee_id=raw_id,
                sequence=sequence,
            )
        )
    return result


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
        raise CommercialValidationError("Approval workflow has not been started")
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
        raise CommercialValidationError("Approval transition is not available")
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
        raise CommercialValidationError("No pending approval request was found")
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
        raise CommercialValidationError(
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


async def submit_measurement_for_certification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    measurement_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MeasurementEntry:
    try:
        await ensure_measurement_certification_workflow(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        before = await db.scalar(
            select(MeasurementEntry).where(
                MeasurementEntry.id == measurement_id,
                MeasurementEntry.organization_id == organization_id,
                MeasurementEntry.project_id == project_id,
            )
        )
        if before is None:
            raise CommercialValidationError("Measurement was not found")
        transition_key = (
            "resubmit" if before.status == MeasurementStatus.REJECTED else "submit"
        )
        row = await transition_measurement(
            db,
            organization_id=organization_id,
            project_id=project_id,
            measurement_id=measurement_id,
            expected_revision=expected_revision,
            target_status=MeasurementStatus.SUBMITTED,
            membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            reason=reason,
        )
        instance = await start_workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=MEASUREMENT_WORKFLOW_KEY,
            entity_type=MEASUREMENT_ENTITY_TYPE,
            entity_id=measurement_id,
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
                "measurement_id": str(measurement_id),
            },
        )
        return row
    except WorkflowConflictError as exc:
        raise CommercialConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise CommercialValidationError(str(exc)) from exc


async def decide_measurement_certification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    measurement_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    approve: bool,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MeasurementEntry:
    try:
        instance = await _workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=MEASUREMENT_WORKFLOW_KEY,
            entity_type=MEASUREMENT_ENTITY_TYPE,
            entity_id=measurement_id,
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
            return await transition_measurement(
                db,
                organization_id=organization_id,
                project_id=project_id,
                measurement_id=measurement_id,
                expected_revision=expected_revision,
                target_status=MeasurementStatus.CERTIFIED,
                membership_id=actor_membership_id,
                actor_user_id=actor_user_id,
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
            return await transition_measurement(
                db,
                organization_id=organization_id,
                project_id=project_id,
                measurement_id=measurement_id,
                expected_revision=expected_revision,
                target_status=MeasurementStatus.REJECTED,
                membership_id=actor_membership_id,
                actor_user_id=actor_user_id,
                session_id=session_id,
                reason=reason,
            )

        row = await db.scalar(
            select(MeasurementEntry).where(
                MeasurementEntry.id == measurement_id,
                MeasurementEntry.organization_id == organization_id,
                MeasurementEntry.project_id == project_id,
            )
        )
        if row is None:
            raise CommercialValidationError("Measurement was not found")
        return row
    except WorkflowConflictError as exc:
        raise CommercialConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise CommercialValidationError(str(exc)) from exc


async def submit_ra_bill_for_certification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    bill_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> RABill:
    try:
        await ensure_ra_bill_certification_workflow(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        row = await transition_ra_bill(
            db,
            organization_id=organization_id,
            project_id=project_id,
            bill_id=bill_id,
            expected_revision=expected_revision,
            target_status=RABillStatus.SUBMITTED,
            membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            reason=reason,
        )
        instance = await start_workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=RA_BILL_WORKFLOW_KEY,
            entity_type=RA_BILL_ENTITY_TYPE,
            entity_id=bill_id,
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
                "ra_bill_id": str(bill_id),
            },
        )
        return row
    except WorkflowConflictError as exc:
        raise CommercialConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise CommercialValidationError(str(exc)) from exc


async def decide_ra_bill_certification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    bill_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    approve: bool,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> RABill:
    try:
        instance = await _workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=RA_BILL_WORKFLOW_KEY,
            entity_type=RA_BILL_ENTITY_TYPE,
            entity_id=bill_id,
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
            return await transition_ra_bill(
                db,
                organization_id=organization_id,
                project_id=project_id,
                bill_id=bill_id,
                expected_revision=expected_revision,
                target_status=RABillStatus.CERTIFIED,
                membership_id=actor_membership_id,
                actor_user_id=actor_user_id,
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
            return await transition_ra_bill(
                db,
                organization_id=organization_id,
                project_id=project_id,
                bill_id=bill_id,
                expected_revision=expected_revision,
                target_status=RABillStatus.DRAFT,
                membership_id=actor_membership_id,
                actor_user_id=actor_user_id,
                session_id=session_id,
                reason=reason,
            )

        row = await db.scalar(
            select(RABill).where(
                RABill.id == bill_id,
                RABill.organization_id == organization_id,
                RABill.project_id == project_id,
            )
        )
        if row is None:
            raise CommercialValidationError("RA bill was not found")
        return row
    except WorkflowConflictError as exc:
        raise CommercialConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise CommercialValidationError(str(exc)) from exc
