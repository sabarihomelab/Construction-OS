from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import (
    BOQ,
    BOQItem,
    BOQStatus,
    RABill,
    RABillLine,
    RABillStatus,
)
from app.modules.financials.commitment_models import ProjectCommitmentAllocation
from app.modules.financials.commercial_control_schemas import (
    BOQCommercialControlLine,
    BOQCommercialControlSummary,
)
from app.modules.financials.job_cost_models import (
    ProjectCostAllocation,
    ProjectCostEntry,
    ProjectCostStatus,
)
from app.modules.financials.models import CommitmentStatus, ProjectCommitment
from app.modules.financials.service import FinancialValidationError, _require_project


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def build_boq_commercial_control(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> BOQCommercialControlSummary:
    project = await _require_project(db, organization_id, project_id)
    currency_code = (project.currency_code or "INR").upper()

    boq_items = list(
        (
            await db.scalars(
                select(BOQItem)
                .join(
                    BOQ,
                    (BOQ.id == BOQItem.boq_id)
                    & (BOQ.project_id == BOQItem.project_id)
                    & (BOQ.organization_id == BOQItem.organization_id),
                )
                .where(
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQ.status == BOQStatus.APPROVED,
                    BOQ.currency_code == currency_code,
                )
                .order_by(BOQItem.boq_id, BOQItem.line_number)
            )
        ).all()
    )
    if not boq_items:
        raise FinancialValidationError(
            "Project has no approved BOQ in the project currency for commercial control"
        )

    commitment_rows = await db.execute(
        select(
            ProjectCommitmentAllocation.boq_item_id,
            func.coalesce(func.sum(ProjectCommitmentAllocation.committed_amount), 0),
        )
        .join(
            ProjectCommitment,
            ProjectCommitment.id == ProjectCommitmentAllocation.commitment_id,
        )
        .where(
            ProjectCommitmentAllocation.organization_id == organization_id,
            ProjectCommitmentAllocation.project_id == project_id,
            ProjectCommitmentAllocation.boq_item_id.is_not(None),
            ProjectCommitment.status != CommitmentStatus.CANCELLED,
        )
        .group_by(ProjectCommitmentAllocation.boq_item_id)
    )
    commitments = {
        boq_item_id: _money(Decimal(amount))
        for boq_item_id, amount in commitment_rows.all()
    }

    actual_rows = await db.execute(
        select(
            ProjectCostAllocation.boq_item_id,
            func.coalesce(func.sum(ProjectCostAllocation.amount), 0),
        )
        .join(ProjectCostEntry, ProjectCostEntry.id == ProjectCostAllocation.cost_entry_id)
        .where(
            ProjectCostAllocation.organization_id == organization_id,
            ProjectCostAllocation.project_id == project_id,
            ProjectCostAllocation.boq_item_id.is_not(None),
            ProjectCostEntry.status == ProjectCostStatus.POSTED,
        )
        .group_by(ProjectCostAllocation.boq_item_id)
    )
    actuals = {
        boq_item_id: _money(Decimal(amount))
        for boq_item_id, amount in actual_rows.all()
    }

    billed_rows = await db.execute(
        select(
            RABillLine.boq_item_id,
            func.coalesce(func.sum(RABillLine.gross_amount), 0),
        )
        .join(RABill, RABill.id == RABillLine.ra_bill_id)
        .where(
            RABillLine.organization_id == organization_id,
            RABillLine.project_id == project_id,
            RABill.status.in_({RABillStatus.CERTIFIED, RABillStatus.PAID}),
            RABill.currency_code == currency_code,
        )
        .group_by(RABillLine.boq_item_id)
    )
    billed = {
        boq_item_id: _money(Decimal(amount))
        for boq_item_id, amount in billed_rows.all()
    }

    lines: list[BOQCommercialControlLine] = []
    for item in boq_items:
        boq_amount = _money(item.amount)
        committed_amount = commitments.get(item.id, Decimal("0.00"))
        actual_cost = actuals.get(item.id, Decimal("0.00"))
        certified_billed_amount = billed.get(item.id, Decimal("0.00"))
        lines.append(
            BOQCommercialControlLine(
                boq_item_id=item.id,
                boq_id=item.boq_id,
                wbs_code_id=item.wbs_code_id,
                line_number=item.line_number,
                item_code=item.item_code,
                description=item.description,
                unit_code=item.unit_code,
                boq_quantity=item.quantity,
                boq_rate=item.rate,
                boq_amount=boq_amount,
                committed_amount=committed_amount,
                actual_cost=actual_cost,
                certified_billed_amount=certified_billed_amount,
                uncommitted_budget=_money(boq_amount - committed_amount),
                commitment_remaining=_money(committed_amount - actual_cost),
                budget_remaining=_money(boq_amount - actual_cost),
                unbilled_boq_value=_money(boq_amount - certified_billed_amount),
            )
        )

    return BOQCommercialControlSummary(
        project_id=project_id,
        currency_code=currency_code,
        total_boq_amount=_money(sum((line.boq_amount for line in lines), Decimal(0))),
        total_committed_amount=_money(
            sum((line.committed_amount for line in lines), Decimal(0))
        ),
        total_actual_cost=_money(sum((line.actual_cost for line in lines), Decimal(0))),
        total_certified_billed_amount=_money(
            sum((line.certified_billed_amount for line in lines), Decimal(0))
        ),
        total_uncommitted_budget=_money(
            sum((line.uncommitted_budget for line in lines), Decimal(0))
        ),
        total_commitment_remaining=_money(
            sum((line.commitment_remaining for line in lines), Decimal(0))
        ),
        total_budget_remaining=_money(
            sum((line.budget_remaining for line in lines), Decimal(0))
        ),
        total_unbilled_boq_value=_money(
            sum((line.unbilled_boq_value for line in lines), Decimal(0))
        ),
        lines=lines,
    )
