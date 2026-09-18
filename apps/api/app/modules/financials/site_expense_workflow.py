from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authorization.models import MembershipRole, Role
from app.modules.financials.job_cost_models import SiteExpense, SiteExpenseStatus
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    review_site_expense,
    submit_site_expense,
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

SITE_EXPENSE_WORKFLOW_KEY = "financials.site_expense.approval"
SITE_EXPENSE_ENTITY_TYPE = "site_expense"
DEFAULT_APPROVER_ROLE_KEY = "project-manager"


async def ensure_site_expense_approval_workflow(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WorkflowDefinition:
    definition = await db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.organization_id == organization_id,
            WorkflowDefinition.key == SITE_EXPENSE_WORKFLOW_KEY,
        )
    )
    if definition is not None:
        if not definition.active or definition.current_version < 1:
            raise FinancialValidationError(
                "Site expense approval workflow exists but is not published"
            )
        return definition

    definition = WorkflowDefinition(
        organization_id=organization_id,
        key=SITE_EXPENSE_WORKFLOW_KEY,
        entity_type=SITE_EXPENSE_ENTITY_TYPE,
        name="Site Expense Approval",
        description="Default India-first site expense approval workflow.",
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
                "assignee_type": ApprovalAssigneeType.PROJECT_ROLE.value,
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
                name="Submit site expense",
                from_state_key="draft",
                to_state_key="submitted",
                required_permission_key="financials.site_expense.create",
            ),
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="resubmit",
                name="Resubmit site expense",
                from_state_key="rejected",
                to_state_key="submitted",
                required_permission_key="financials.site_expense.create",
            ),
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="approve",
                name="Approve site expense",
                from_state_key="submitted",
                to_state_key="approved",
                approval_policy={"mode": "sequential"},
                assignment_rule=assignment_rule,
            ),
            WorkflowTransition(
                organization_id=organization_id,
                workflow_version_id=version.id,
                key="reject",
                name="Reject site expense",
                from_state_key="submitted",
                to_state_key="rejected",
                required_permission_key="financials.site_expense.approve",
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
    raw_assignees = assignment_rule.get("assignees")
    if not isinstance(raw_assignees, list) or not raw_assignees:
        raise FinancialValidationError("Approval workflow has no configured assignee")

    assignees: list[ApprovalAssignee] = []
    for raw in raw_assignees:
        if not isinstance(raw, dict):
            raise FinancialValidationError("Approval workflow assignee is invalid")
        raw_type = raw.get("assignee_type")
        raw_id = raw.get("assignee_id")
        if not isinstance(raw_type, str) or not isinstance(raw_id, str):
            raise FinancialValidationError("Approval workflow assignee is invalid")
        try:
            assignees.append(
                ApprovalAssignee(
                    assignee_type=ApprovalAssigneeType(raw_type),
                    assignee_id=raw_id,
                    sequence=int(raw.get("sequence", 1)),
                )
            )
        except (TypeError, ValueError) as exc:
            raise FinancialValidationError("Approval workflow assignee is invalid") from exc
    return assignees


async def _workflow_instance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    expense_id: UUID,
) -> WorkflowInstance:
    instance = await db.scalar(
        select(WorkflowInstance)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowInstance.definition_id)
        .where(
            WorkflowInstance.organization_id == organization_id,
            WorkflowInstance.entity_type == SITE_EXPENSE_ENTITY_TYPE,
            WorkflowInstance.entity_id == expense_id,
            WorkflowDefinition.key == SITE_EXPENSE_WORKFLOW_KEY,
        )
    )
    if instance is None:
        raise FinancialValidationError("Site expense approval workflow has not been started")
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
        raise FinancialValidationError("Site expense approval transition is not available")
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
        raise FinancialValidationError("No pending site expense approval was found")
    return request


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
        (ApprovalAssigneeType.ROLE, key) for key in organization_role_keys
    } | {
        (ApprovalAssigneeType.PROJECT_ROLE, key) for key in project_role_keys
    }
    eligible.add((ApprovalAssigneeType.USER, str(actor_user_id)))
    if "admin.workflow.manage" in permission_keys:
        eligible.update((task.assignee_type, task.assignee_id) for task in pending_tasks)
    return eligible


async def submit_site_expense_for_approval(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SiteExpense:
    try:
        await ensure_site_expense_approval_workflow(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
        before = await db.scalar(
            select(SiteExpense).where(
                SiteExpense.id == expense_id,
                SiteExpense.organization_id == organization_id,
                SiteExpense.project_id == project_id,
            )
        )
        if before is None:
            raise FinancialValidationError("Site expense was not found")
        transition_key = (
            "resubmit" if before.status == SiteExpenseStatus.REJECTED else "submit"
        )
        expense = await submit_site_expense(
            db,
            organization_id=organization_id,
            project_id=project_id,
            expense_id=expense_id,
            expected_revision=expected_revision,
            membership_id=actor_membership_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            reason=reason,
        )
        instance = await start_workflow_instance(
            db,
            organization_id=organization_id,
            definition_key=SITE_EXPENSE_WORKFLOW_KEY,
            entity_type=SITE_EXPENSE_ENTITY_TYPE,
            entity_id=expense_id,
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
                "site_expense_id": str(expense_id),
            },
        )
        return expense
    except WorkflowConflictError as exc:
        raise FinancialConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise FinancialValidationError(str(exc)) from exc


async def decide_site_expense_approval(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
    expected_revision: int,
    permission_keys: set[str],
    actor_user_id: UUID,
    actor_membership_id: UUID,
    approve: bool,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SiteExpense:
    try:
        instance = await _workflow_instance(
            db,
            organization_id=organization_id,
            expense_id=expense_id,
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
            raise FinancialValidationError(
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
            return await review_site_expense(
                db,
                organization_id=organization_id,
                project_id=project_id,
                expense_id=expense_id,
                expected_revision=expected_revision,
                approve=True,
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
            return await review_site_expense(
                db,
                organization_id=organization_id,
                project_id=project_id,
                expense_id=expense_id,
                expected_revision=expected_revision,
                approve=False,
                membership_id=actor_membership_id,
                actor_user_id=actor_user_id,
                session_id=session_id,
                reason=reason,
            )

        expense = await db.scalar(
            select(SiteExpense).where(
                SiteExpense.id == expense_id,
                SiteExpense.organization_id == organization_id,
                SiteExpense.project_id == project_id,
            )
        )
        if expense is None:
            raise FinancialValidationError("Site expense was not found")
        return expense
    except WorkflowConflictError as exc:
        raise FinancialConflictError(str(exc)) from exc
    except (WorkflowPermissionError, WorkflowValidationError) as exc:
        raise FinancialValidationError(str(exc)) from exc
