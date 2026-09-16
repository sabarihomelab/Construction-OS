from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import WBSCode
from app.modules.estimating.models import BudgetCategory, BudgetLine, BudgetStatus, ProjectBudget
from app.modules.financials.budget_control_schemas import (
    BudgetCommercialControlLine,
    BudgetCommercialControlSummary,
)
from app.modules.financials.commitment_models import ProjectCommitmentAllocation
from app.modules.financials.job_cost_models import (
    CostHead,
    CostHeadCategory,
    ProjectCostAllocation,
    ProjectCostEntry,
    ProjectCostStatus,
)
from app.modules.financials.models import (
    CommitmentSourceType,
    CommitmentStatus,
    ProjectCommitment,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    _require_project,
)

ZERO = Decimal("0.00")


COST_HEAD_TO_BUDGET_CATEGORY: dict[CostHeadCategory, BudgetCategory] = {
    CostHeadCategory.MATERIAL: BudgetCategory.MATERIAL,
    CostHeadCategory.LABOUR: BudgetCategory.LABOUR,
    CostHeadCategory.EQUIPMENT: BudgetCategory.EQUIPMENT,
    CostHeadCategory.SUBCONTRACT: BudgetCategory.SUBCONTRACT,
    CostHeadCategory.SITE_EXPENSE: BudgetCategory.OTHER,
    CostHeadCategory.INDIRECT: BudgetCategory.OVERHEAD,
    CostHeadCategory.OTHER: BudgetCategory.OTHER,
}


COMMITMENT_TO_BUDGET_CATEGORY: dict[CommitmentSourceType, BudgetCategory] = {
    CommitmentSourceType.PURCHASE_ORDER: BudgetCategory.MATERIAL,
    CommitmentSourceType.SUBCONTRACT: BudgetCategory.SUBCONTRACT,
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def build_budget_commercial_control(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> BudgetCommercialControlSummary:
    project = await _require_project(db, organization_id, project_id)
    project_currency = (project.currency_code or "INR").upper()

    budgets = list(
        (
            await db.scalars(
                select(ProjectBudget).where(
                    ProjectBudget.organization_id == organization_id,
                    ProjectBudget.project_id == project_id,
                    ProjectBudget.status == BudgetStatus.APPROVED,
                )
            )
        ).all()
    )
    if not budgets:
        raise FinancialValidationError("Project has no approved budget baseline")
    if len(budgets) > 1:
        raise FinancialConflictError("Project has multiple approved budget baselines")
    budget = budgets[0]
    currency_code = budget.currency_code.upper()
    if currency_code != project_currency:
        raise FinancialValidationError("Approved budget currency must match the project currency")

    foreign_commitment_count = int(
        await db.scalar(
            select(func.count(ProjectCommitment.id)).where(
                ProjectCommitment.organization_id == organization_id,
                ProjectCommitment.project_id == project_id,
                ProjectCommitment.status != CommitmentStatus.CANCELLED,
                ProjectCommitment.currency_code != currency_code,
            )
        )
        or 0
    )
    foreign_actual_count = int(
        await db.scalar(
            select(func.count(ProjectCostEntry.id)).where(
                ProjectCostEntry.organization_id == organization_id,
                ProjectCostEntry.project_id == project_id,
                ProjectCostEntry.status == ProjectCostStatus.POSTED,
                ProjectCostEntry.currency_code != currency_code,
            )
        )
        or 0
    )
    if foreign_commitment_count or foreign_actual_count:
        raise FinancialValidationError(
            "Budget control cannot combine project commitments or actual costs in different currencies"
        )

    wbs_rows = list(
        (
            await db.scalars(
                select(WBSCode).where(
                    WBSCode.organization_id == organization_id,
                    WBSCode.project_id == project_id,
                )
            )
        ).all()
    )
    wbs_by_id = {row.id: row for row in wbs_rows}

    dimensions: dict[tuple[UUID, BudgetCategory], dict[str, object]] = {}
    budget_rows = list(
        (
            await db.scalars(
                select(BudgetLine)
                .where(
                    BudgetLine.organization_id == organization_id,
                    BudgetLine.project_id == project_id,
                    BudgetLine.budget_id == budget.id,
                )
                .order_by(BudgetLine.wbs_code_id, BudgetLine.category)
            )
        ).all()
    )
    if not budget_rows:
        raise FinancialValidationError("Approved budget has no budget lines")

    for row in budget_rows:
        wbs = wbs_by_id.get(row.wbs_code_id)
        if wbs is None:
            raise FinancialConflictError("Approved budget references a missing WBS code")
        key = (row.wbs_code_id, row.category)
        dimensions[key] = {
            "wbs": wbs,
            "category": row.category,
            "has_budget_line": True,
            "budget_amount": _money(Decimal(row.amount)),
            "committed_amount": ZERO,
            "actual_cost": ZERO,
        }

    unallocated_commitment_amount = ZERO
    commitment_rows = await db.execute(
        select(
            ProjectCommitmentAllocation.wbs_code_id,
            ProjectCommitment.source_type,
            func.coalesce(func.sum(ProjectCommitmentAllocation.committed_amount), 0),
        )
        .join(
            ProjectCommitment,
            ProjectCommitment.id == ProjectCommitmentAllocation.commitment_id,
        )
        .where(
            ProjectCommitmentAllocation.organization_id == organization_id,
            ProjectCommitmentAllocation.project_id == project_id,
            ProjectCommitment.status != CommitmentStatus.CANCELLED,
            ProjectCommitment.currency_code == currency_code,
        )
        .group_by(ProjectCommitmentAllocation.wbs_code_id, ProjectCommitment.source_type)
    )
    for wbs_code_id, source_type, amount in commitment_rows.all():
        normalized_amount = _money(Decimal(amount))
        if wbs_code_id is None:
            unallocated_commitment_amount = _money(
                unallocated_commitment_amount + normalized_amount
            )
            continue
        category = COMMITMENT_TO_BUDGET_CATEGORY[source_type]
        wbs = wbs_by_id.get(wbs_code_id)
        if wbs is None:
            raise FinancialConflictError("Commitment references a missing WBS code")
        key = (wbs_code_id, category)
        dimension = dimensions.setdefault(
            key,
            {
                "wbs": wbs,
                "category": category,
                "has_budget_line": False,
                "budget_amount": ZERO,
                "committed_amount": ZERO,
                "actual_cost": ZERO,
            },
        )
        dimension["committed_amount"] = _money(
            Decimal(dimension["committed_amount"]) + normalized_amount
        )

    unallocated_actual_cost = ZERO
    actual_rows = await db.execute(
        select(
            ProjectCostAllocation.wbs_code_id,
            CostHead.category,
            func.coalesce(func.sum(ProjectCostAllocation.amount), 0),
        )
        .join(ProjectCostEntry, ProjectCostEntry.id == ProjectCostAllocation.cost_entry_id)
        .join(CostHead, CostHead.id == ProjectCostAllocation.cost_head_id)
        .where(
            ProjectCostAllocation.organization_id == organization_id,
            ProjectCostAllocation.project_id == project_id,
            ProjectCostEntry.status == ProjectCostStatus.POSTED,
            ProjectCostEntry.currency_code == currency_code,
        )
        .group_by(ProjectCostAllocation.wbs_code_id, CostHead.category)
    )
    for wbs_code_id, cost_head_category, amount in actual_rows.all():
        normalized_amount = _money(Decimal(amount))
        if wbs_code_id is None:
            unallocated_actual_cost = _money(unallocated_actual_cost + normalized_amount)
            continue
        category = COST_HEAD_TO_BUDGET_CATEGORY[cost_head_category]
        wbs = wbs_by_id.get(wbs_code_id)
        if wbs is None:
            raise FinancialConflictError("Actual cost references a missing WBS code")
        key = (wbs_code_id, category)
        dimension = dimensions.setdefault(
            key,
            {
                "wbs": wbs,
                "category": category,
                "has_budget_line": False,
                "budget_amount": ZERO,
                "committed_amount": ZERO,
                "actual_cost": ZERO,
            },
        )
        dimension["actual_cost"] = _money(
            Decimal(dimension["actual_cost"]) + normalized_amount
        )

    lines: list[BudgetCommercialControlLine] = []
    for dimension in dimensions.values():
        wbs = dimension["wbs"]
        category = dimension["category"]
        budget_amount = _money(Decimal(dimension["budget_amount"]))
        committed_amount = _money(Decimal(dimension["committed_amount"]))
        actual_cost = _money(Decimal(dimension["actual_cost"]))
        forecast_exposure = _money(max(committed_amount, actual_cost))
        lines.append(
            BudgetCommercialControlLine(
                wbs_code_id=wbs.id,
                wbs_code=wbs.code,
                wbs_name=wbs.name,
                category=category,
                has_budget_line=bool(dimension["has_budget_line"]),
                budget_amount=budget_amount,
                committed_amount=committed_amount,
                actual_cost=actual_cost,
                forecast_exposure=forecast_exposure,
                uncommitted_budget=_money(budget_amount - committed_amount),
                commitment_remaining=_money(committed_amount - actual_cost),
                budget_remaining_to_actual=_money(budget_amount - actual_cost),
                forecast_variance=_money(budget_amount - forecast_exposure),
            )
        )
    lines.sort(key=lambda line: (line.wbs_code, line.category.value))

    allocated_commitment = _money(
        sum((line.committed_amount for line in lines), start=Decimal(0))
    )
    allocated_actual = _money(sum((line.actual_cost for line in lines), start=Decimal(0)))
    allocated_forecast = _money(
        sum((line.forecast_exposure for line in lines), start=Decimal(0))
    )
    total_budget = _money(sum((line.budget_amount for line in lines), start=Decimal(0)))
    total_commitment = _money(allocated_commitment + unallocated_commitment_amount)
    total_actual = _money(allocated_actual + unallocated_actual_cost)
    total_forecast = _money(
        allocated_forecast + unallocated_commitment_amount + unallocated_actual_cost
    )
    coverage_complete = (
        unallocated_commitment_amount == ZERO
        and unallocated_actual_cost == ZERO
        and all(
            line.has_budget_line
            for line in lines
            if line.committed_amount != ZERO or line.actual_cost != ZERO
        )
    )

    return BudgetCommercialControlSummary(
        project_id=project_id,
        budget_id=budget.id,
        budget_code=budget.code,
        budget_revision=budget.revision,
        budget_approved_at=budget.approved_at,
        currency_code=currency_code,
        control_coverage_complete=coverage_complete,
        total_budget_amount=total_budget,
        total_committed_amount=total_commitment,
        total_actual_cost=total_actual,
        total_forecast_exposure=total_forecast,
        total_uncommitted_budget=_money(total_budget - total_commitment),
        total_commitment_remaining=_money(total_commitment - total_actual),
        total_budget_remaining_to_actual=_money(total_budget - total_actual),
        total_forecast_variance=_money(total_budget - total_forecast),
        unallocated_commitment_amount=unallocated_commitment_amount,
        unallocated_actual_cost=unallocated_actual_cost,
        lines=lines,
    )
