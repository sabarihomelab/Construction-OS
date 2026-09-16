from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subcontracts.cumulative_schemas import (
    SubcontractClaimCumulativeLine,
    SubcontractClaimCumulativeRead,
)
from app.modules.subcontracts.models import (
    Subcontract,
    SubcontractClaim,
    SubcontractClaimLine,
    SubcontractClaimStatus,
    SubcontractLine,
)
from app.modules.subcontracts.service import SubcontractValidationError


ZERO = Decimal("0.00")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def build_subcontract_claim_cumulative(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subcontract_id: UUID,
    claim_id: UUID,
) -> SubcontractClaimCumulativeRead:
    contract = await db.scalar(
        select(Subcontract).where(
            Subcontract.id == subcontract_id,
            Subcontract.organization_id == organization_id,
            Subcontract.project_id == project_id,
        )
    )
    if contract is None:
        raise SubcontractValidationError("Subcontract was not found")

    claim = await db.scalar(
        select(SubcontractClaim).where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.subcontract_id == subcontract_id,
            SubcontractClaim.organization_id == organization_id,
            SubcontractClaim.project_id == project_id,
        )
    )
    if claim is None:
        raise SubcontractValidationError("Subcontract claim was not found")

    contract_lines = list(
        (
            await db.scalars(
                select(SubcontractLine)
                .where(
                    SubcontractLine.organization_id == organization_id,
                    SubcontractLine.project_id == project_id,
                    SubcontractLine.subcontract_id == subcontract_id,
                )
                .order_by(SubcontractLine.line_number)
            )
        ).all()
    )
    if not contract_lines:
        raise SubcontractValidationError("Subcontract has no scope lines")

    current_lines = list(
        (
            await db.scalars(
                select(SubcontractClaimLine).where(
                    SubcontractClaimLine.organization_id == organization_id,
                    SubcontractClaimLine.project_id == project_id,
                    SubcontractClaimLine.claim_id == claim_id,
                )
            )
        ).all()
    )
    current_by_line = {row.subcontract_line_id: row for row in current_lines}

    prior_rows = await db.execute(
        select(
            SubcontractClaimLine.subcontract_line_id,
            func.coalesce(func.sum(SubcontractClaimLine.certified_quantity), 0),
            func.coalesce(func.sum(SubcontractClaimLine.certified_amount), 0),
        )
        .join(SubcontractClaim, SubcontractClaim.id == SubcontractClaimLine.claim_id)
        .where(
            SubcontractClaimLine.organization_id == organization_id,
            SubcontractClaimLine.project_id == project_id,
            SubcontractClaim.subcontract_id == subcontract_id,
            SubcontractClaim.status.in_(
                {SubcontractClaimStatus.CERTIFIED, SubcontractClaimStatus.PAID}
            ),
            SubcontractClaim.id != claim_id,
            or_(
                SubcontractClaim.period_to < claim.period_to,
                (
                    (SubcontractClaim.period_to == claim.period_to)
                    & (SubcontractClaim.created_at < claim.created_at)
                ),
            ),
        )
        .group_by(SubcontractClaimLine.subcontract_line_id)
    )
    prior_by_line = {
        subcontract_line_id: (Decimal(quantity), _money(Decimal(amount)))
        for subcontract_line_id, quantity, amount in prior_rows.all()
    }

    prior_header = await db.execute(
        select(
            func.coalesce(func.sum(SubcontractClaim.gross_amount), 0),
            func.coalesce(func.sum(SubcontractClaim.paid_amount), 0),
        ).where(
            SubcontractClaim.organization_id == organization_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.subcontract_id == subcontract_id,
            SubcontractClaim.status.in_(
                {SubcontractClaimStatus.CERTIFIED, SubcontractClaimStatus.PAID}
            ),
            SubcontractClaim.id != claim_id,
            or_(
                SubcontractClaim.period_to < claim.period_to,
                (
                    (SubcontractClaim.period_to == claim.period_to)
                    & (SubcontractClaim.created_at < claim.created_at)
                ),
            ),
        )
    )
    previous_certified_gross_raw, previous_paid_raw = prior_header.one()
    previous_certified_gross = _money(Decimal(previous_certified_gross_raw))
    previous_paid = _money(Decimal(previous_paid_raw))

    current_is_certified = claim.status in {
        SubcontractClaimStatus.CERTIFIED,
        SubcontractClaimStatus.PAID,
    }
    lines: list[SubcontractClaimCumulativeLine] = []
    for scope in contract_lines:
        current = current_by_line.get(scope.id)
        previous_quantity, previous_amount = prior_by_line.get(scope.id, (Decimal(0), ZERO))
        claimed_quantity = Decimal(current.claimed_quantity) if current is not None else Decimal(0)
        current_gross = _money(Decimal(current.gross_amount)) if current is not None else ZERO
        current_certified_quantity = (
            Decimal(current.certified_quantity)
            if current is not None and current_is_certified
            else Decimal(0)
        )
        current_certified_amount = (
            _money(Decimal(current.certified_amount))
            if current is not None and current_is_certified
            else ZERO
        )
        cumulative_quantity = previous_quantity + current_certified_quantity
        cumulative_amount = _money(previous_amount + current_certified_amount)
        contract_quantity = Decimal(scope.quantity)
        contract_amount = _money(Decimal(scope.amount))
        lines.append(
            SubcontractClaimCumulativeLine(
                subcontract_line_id=scope.id,
                wbs_code_id=scope.wbs_code_id,
                boq_item_id=scope.boq_item_id,
                line_number=scope.line_number,
                description=scope.description,
                unit_code=scope.unit_code,
                contract_quantity=contract_quantity,
                contract_rate=scope.rate,
                contract_amount=contract_amount,
                previous_certified_quantity=previous_quantity,
                previous_certified_amount=previous_amount,
                current_claimed_quantity=claimed_quantity,
                current_gross_amount=current_gross,
                current_certified_quantity=current_certified_quantity,
                current_certified_amount=current_certified_amount,
                cumulative_certified_quantity=cumulative_quantity,
                cumulative_certified_amount=cumulative_amount,
                remaining_quantity=contract_quantity - cumulative_quantity,
                remaining_amount=_money(contract_amount - cumulative_amount),
            )
        )

    current_certified_gross = (
        _money(Decimal(claim.gross_amount)) if current_is_certified else ZERO
    )
    return SubcontractClaimCumulativeRead(
        project_id=project_id,
        subcontract_id=subcontract_id,
        claim_id=claim.id,
        claim_number=claim.number,
        claim_status=claim.status,
        currency_code=contract.currency_code,
        previous_certified_gross=previous_certified_gross,
        current_gross_amount=_money(Decimal(claim.gross_amount)),
        current_certified_gross=current_certified_gross,
        cumulative_certified_gross=_money(previous_certified_gross + current_certified_gross),
        current_retention_amount=_money(Decimal(claim.retention_amount)),
        current_other_deductions=_money(Decimal(claim.other_deductions)),
        current_tax_withheld_amount=_money(Decimal(claim.tax_withheld_amount)),
        current_net_certified=_money(Decimal(claim.certified_amount)),
        current_paid_amount=_money(Decimal(claim.paid_amount)),
        cumulative_paid_amount=_money(previous_paid + Decimal(claim.paid_amount)),
        lines=lines,
    )
