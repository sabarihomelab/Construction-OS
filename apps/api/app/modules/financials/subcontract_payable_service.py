from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.financials.subcontract_payable_schemas import (
    SubcontractPayableLineRead,
    SubcontractPayableRead,
)
from app.modules.subcontracts.models import (
    Subcontract,
    SubcontractClaim,
    SubcontractClaimLine,
    SubcontractClaimStatus,
    SubcontractLine,
)


class SubcontractPayableProjectionError(ValueError):
    pass


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


async def _build_payable(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim: SubcontractClaim,
) -> SubcontractPayableRead:
    if claim.status not in {
        SubcontractClaimStatus.CERTIFIED,
        SubcontractClaimStatus.PAID,
    }:
        raise SubcontractPayableProjectionError(
            "Only certified subcontract claims have a payable basis"
        )
    if claim.certified_at is None:
        raise SubcontractPayableProjectionError(
            "Certified subcontract claim is missing certification evidence"
        )

    subcontract = await db.scalar(
        select(Subcontract).where(
            Subcontract.id == claim.subcontract_id,
            Subcontract.organization_id == organization_id,
            Subcontract.project_id == project_id,
        )
    )
    if subcontract is None:
        raise SubcontractPayableProjectionError(
            "Subcontract was not found for certified claim"
        )

    claim_lines = list(
        (
            await db.scalars(
                select(SubcontractClaimLine)
                .where(
                    SubcontractClaimLine.organization_id == organization_id,
                    SubcontractClaimLine.project_id == project_id,
                    SubcontractClaimLine.claim_id == claim.id,
                    SubcontractClaimLine.certified_amount > 0,
                )
                .order_by(SubcontractClaimLine.id)
            )
        ).all()
    )
    contract_line_ids = {line.subcontract_line_id for line in claim_lines}
    contract_lines = {}
    if contract_line_ids:
        contract_lines = {
            line.id: line
            for line in (
                await db.scalars(
                    select(SubcontractLine).where(
                        SubcontractLine.organization_id == organization_id,
                        SubcontractLine.project_id == project_id,
                        SubcontractLine.subcontract_id == subcontract.id,
                        SubcontractLine.id.in_(contract_line_ids),
                    )
                )
            ).all()
        }
    if len(contract_lines) != len(contract_line_ids):
        raise SubcontractPayableProjectionError(
            "Certified claim is missing authoritative work-order lineage"
        )

    lines = [
        SubcontractPayableLineRead(
            claim_line_id=claim_line.id,
            subcontract_line_id=claim_line.subcontract_line_id,
            measurement_entry_id=claim_line.measurement_entry_id,
            wbs_code_id=contract_lines[claim_line.subcontract_line_id].wbs_code_id,
            boq_item_id=contract_lines[claim_line.subcontract_line_id].boq_item_id,
            description=contract_lines[claim_line.subcontract_line_id].description,
            unit_code=contract_lines[claim_line.subcontract_line_id].unit_code,
            certified_quantity=claim_line.certified_quantity,
            rate=claim_line.rate,
            certified_amount=claim_line.certified_amount,
        )
        for claim_line in claim_lines
    ]

    gross = _money(sum((line.certified_amount for line in claim_lines), start=Decimal(0)))
    if gross != _money(claim.gross_amount):
        raise SubcontractPayableProjectionError(
            "Certified claim gross amount does not reconcile to certified lines"
        )
    net = _money(claim.certified_amount)
    paid = _money(claim.paid_amount)
    if paid > net:
        raise SubcontractPayableProjectionError(
            "Recorded payment exceeds certified payable"
        )

    return SubcontractPayableRead(
        claim_id=claim.id,
        claim_number=claim.number,
        subcontract_id=subcontract.id,
        subcontract_number=subcontract.number,
        contractor_party_id=subcontract.contractor_party_id,
        period_from=claim.period_from,
        period_to=claim.period_to,
        status=claim.status,
        currency_code=subcontract.currency_code.upper(),
        gross_certified_work=gross,
        retention_amount=_money(claim.retention_amount),
        other_deductions=_money(claim.other_deductions),
        tax_withheld_amount=_money(claim.tax_withheld_amount),
        net_certified_payable=net,
        paid_amount=paid,
        outstanding_amount=_money(net - paid),
        certified_at=claim.certified_at,
        lines=lines,
    )


async def list_subcontract_payables(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[SubcontractPayableRead]:
    claims = list(
        (
            await db.scalars(
                select(SubcontractClaim)
                .where(
                    SubcontractClaim.organization_id == organization_id,
                    SubcontractClaim.project_id == project_id,
                    SubcontractClaim.status.in_(
                        {
                            SubcontractClaimStatus.CERTIFIED,
                            SubcontractClaimStatus.PAID,
                        }
                    ),
                )
                .order_by(SubcontractClaim.period_to.desc(), SubcontractClaim.number)
            )
        ).all()
    )
    return [
        await _build_payable(
            db,
            organization_id=organization_id,
            project_id=project_id,
            claim=claim,
        )
        for claim in claims
    ]


async def get_subcontract_payable(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
) -> SubcontractPayableRead:
    claim = await db.scalar(
        select(SubcontractClaim).where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.organization_id == organization_id,
            SubcontractClaim.project_id == project_id,
        )
    )
    if claim is None:
        raise SubcontractPayableProjectionError("Subcontract claim was not found")
    return await _build_payable(
        db,
        organization_id=organization_id,
        project_id=project_id,
        claim=claim,
    )
