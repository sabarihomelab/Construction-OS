from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import WBSCode
from app.modules.events.service import enqueue_event
from app.modules.financials.job_cost_models import (
    CostHead,
    CostHeadCategory,
    ProjectCostAllocation,
    ProjectCostEntry,
    ProjectCostSourceType,
    ProjectCostStatus,
)
from app.modules.financials.models import RecordStatus
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    _next_project_number,
    _require_project_membership,
)
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index
from app.modules.workforce.models import (
    ProjectWorkerAssignment,
    ProjectWorkerRate,
    Timecard,
    TimecardStatus,
    TimeEntry,
    WageBasis,
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def _hourly_rate_for_date(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    worker_id: UUID,
    work_date: date,
) -> ProjectWorkerRate:
    rate = await db.scalar(
        select(ProjectWorkerRate)
        .where(
            ProjectWorkerRate.organization_id == organization_id,
            ProjectWorkerRate.project_id == project_id,
            ProjectWorkerRate.assignment_id == assignment_id,
            ProjectWorkerRate.worker_id == worker_id,
            ProjectWorkerRate.effective_from <= work_date,
            (ProjectWorkerRate.effective_to.is_(None))
            | (ProjectWorkerRate.effective_to >= work_date),
        )
        .order_by(ProjectWorkerRate.effective_from.desc())
    )
    if rate is None:
        raise FinancialValidationError(
            f"No project Worker rate is effective on {work_date.isoformat()}"
        )
    if rate.wage_basis != WageBasis.HOURLY:
        raise FinancialValidationError(
            "Approved timecards can be auto-costed only for hourly Worker rates. "
            "Daily, weekly, monthly, piece-rate and contract labour require an explicit "
            "approved costing rule/source so Construction OS does not guess payroll logic."
        )
    return rate


def _entry_cost(entry: TimeEntry, rate: ProjectWorkerRate) -> Decimal:
    if entry.overtime_hours and rate.overtime_rate is None:
        raise FinancialValidationError(
            "Time entry contains overtime but the effective Worker rate has no overtime rate"
        )
    if entry.double_time_hours and rate.double_time_rate is None:
        raise FinancialValidationError(
            "Time entry contains double-time hours but the effective Worker rate has no double-time rate"
        )
    amount = entry.regular_hours * rate.regular_rate
    if entry.overtime_hours:
        amount += entry.overtime_hours * (rate.overtime_rate or Decimal(0))
    if entry.double_time_hours:
        amount += entry.double_time_hours * (rate.double_time_rate or Decimal(0))
    return _money(amount)


async def post_approved_timecard_labour_cost(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    timecard_id: UUID,
    labour_cost_head_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectCostEntry:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise FinancialValidationError("Project was not found")

    existing = await db.scalar(
        select(ProjectCostEntry).where(
            ProjectCostEntry.organization_id == organization_id,
            ProjectCostEntry.project_id == project_id,
            ProjectCostEntry.source_type == ProjectCostSourceType.WORKFORCE_TIME,
            ProjectCostEntry.source_id == timecard_id,
        )
    )
    if existing is not None:
        if existing.status == ProjectCostStatus.POSTED:
            return existing
        raise FinancialConflictError("This timecard already has a non-posted project cost record")

    timecard = await db.scalar(
        select(Timecard).where(
            Timecard.id == timecard_id,
            Timecard.organization_id == organization_id,
            Timecard.project_id == project_id,
        )
    )
    if timecard is None:
        raise FinancialValidationError("Timecard was not found in this project")
    if timecard.status != TimecardStatus.APPROVED:
        raise FinancialValidationError("Only an approved timecard can become project labour cost")

    assignment = await db.scalar(
        select(ProjectWorkerAssignment).where(
            ProjectWorkerAssignment.organization_id == organization_id,
            ProjectWorkerAssignment.project_id == project_id,
            ProjectWorkerAssignment.worker_id == timecard.worker_id,
        )
    )
    if assignment is None:
        raise FinancialValidationError("The timecard Worker has no matching project assignment")

    cost_head = await db.scalar(
        select(CostHead).where(
            CostHead.id == labour_cost_head_id,
            CostHead.organization_id == organization_id,
        )
    )
    if (
        cost_head is None
        or cost_head.status != RecordStatus.ACTIVE
        or not cost_head.allows_posting
        or cost_head.category != CostHeadCategory.LABOUR
    ):
        raise FinancialValidationError("Labour costing requires an active posting Labour Cost Head")

    entries = list(
        (
            await db.scalars(
                select(TimeEntry)
                .where(
                    TimeEntry.organization_id == organization_id,
                    TimeEntry.timecard_id == timecard.id,
                )
                .order_by(TimeEntry.work_date, TimeEntry.created_at, TimeEntry.id)
            )
        ).all()
    )
    if not entries:
        raise FinancialValidationError("Approved timecard has no time entries to cost")

    currency_code = (project.currency_code or "INR").upper()
    prepared: list[tuple[TimeEntry, ProjectWorkerRate, WBSCode | None, Decimal]] = []
    rate_snapshots: list[dict[str, object]] = []
    total_amount = Decimal(0)

    for entry in entries:
        rate = await _hourly_rate_for_date(
            db,
            organization_id=organization_id,
            project_id=project_id,
            assignment_id=assignment.id,
            worker_id=timecard.worker_id,
            work_date=entry.work_date,
        )
        if rate.currency_code.upper() != currency_code:
            raise FinancialValidationError(
                "Worker rate currency must match project currency before labour cost can be posted"
            )

        cost_code = (entry.cost_code or assignment.default_cost_code or "").strip()
        wbs = None
        if cost_code:
            wbs = await db.scalar(
                select(WBSCode).where(
                    WBSCode.organization_id == organization_id,
                    WBSCode.project_id == project_id,
                    WBSCode.code == cost_code,
                )
            )
            if wbs is None:
                raise FinancialValidationError(
                    f"Time entry cost code {cost_code!r} does not match a WBS/Cost Code in this project"
                )

        amount = _entry_cost(entry, rate)
        total_amount += amount
        prepared.append((entry, rate, wbs, amount))
        rate_snapshots.append(
            {
                "work_date": entry.work_date.isoformat(),
                "rate_id": str(rate.id),
                "rate_revision": rate.revision,
                "wage_basis": rate.wage_basis.value,
                "regular_rate": str(rate.regular_rate),
                "overtime_rate": str(rate.overtime_rate) if rate.overtime_rate is not None else None,
                "double_time_rate": (
                    str(rate.double_time_rate) if rate.double_time_rate is not None else None
                ),
                "currency_code": rate.currency_code,
            }
        )

    total_amount = _money(total_amount)
    if total_amount <= 0:
        raise FinancialValidationError("Approved timecard produces no positive labour cost")

    entry_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="project_cost",
        prefix="COST",
    )
    cost_entry = ProjectCostEntry(
        organization_id=organization_id,
        project_id=project_id,
        entry_number=entry_number,
        entry_date=max(item.work_date for item in entries),
        source_type=ProjectCostSourceType.WORKFORCE_TIME,
        source_id=timecard.id,
        source_reference=f"Timecard {timecard.week_start.isoformat()}",
        description=f"Approved labour time for Worker {timecard.worker_id}",
        total_amount=total_amount,
        currency_code=currency_code,
        status=ProjectCostStatus.POSTED,
        configuration_context={
            "timecard_id": str(timecard.id),
            "timecard_revision": timecard.revision,
            "project_worker_assignment_id": str(assignment.id),
            "labour_cost_head_id": str(cost_head.id),
            "rate_snapshots": rate_snapshots,
        },
        revision=1,
        posted_by_membership_id=membership_id,
        posted_at=timecard.approved_at,
    )
    db.add(cost_entry)
    await db.flush()

    for line_number, (entry, rate, wbs, amount) in enumerate(prepared, start=1):
        total_hours = entry.regular_hours + entry.overtime_hours + entry.double_time_hours
        db.add(
            ProjectCostAllocation(
                organization_id=organization_id,
                project_id=project_id,
                cost_entry_id=cost_entry.id,
                line_number=line_number,
                cost_head_id=cost_head.id,
                wbs_code_id=wbs.id if wbs is not None else None,
                party_id=assignment.employer_party_id,
                worker_assignment_id=assignment.id,
                description=f"Labour {entry.work_date.isoformat()} · rate {rate.id}",
                quantity=total_hours,
                unit_code="hour",
                amount=amount,
            )
        )

    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.project_cost.workforce.posted",
        target_type="project_cost_entry",
        target_id=str(cost_entry.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "timecard_id": str(timecard.id),
            "worker_assignment_id": str(assignment.id),
            "amount": total_amount,
            "currency_code": currency_code,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.project_cost.posted",
        entity_type="project_cost_entry",
        entity_id=cost_entry.id,
        entity_version=cost_entry.revision,
        required_permission_key="financials.project_cost.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "source_type": ProjectCostSourceType.WORKFORCE_TIME.value,
            "source_id": str(timecard.id),
            "amount": str(total_amount),
        },
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="project_cost_entry",
        entity_id=cost_entry.id,
        entity_version=cost_entry.revision,
    )
    return cost_entry
