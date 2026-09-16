from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import MeasurementEntry, MeasurementStatus
from app.modules.subcontracts.models import (
    SubcontractClaim,
    SubcontractClaimLine,
    SubcontractClaimStatus,
    SubcontractLine,
)
from app.modules.subcontracts.service import (
    SubcontractValidationError,
)
from app.modules.subcontracts.service import (
    add_claim_line as _add_claim_line,
)
from app.modules.subcontracts.service import (
    certify_claim as _certify_claim,
)

_CLOSED_CLAIM_STATUSES = {
    SubcontractClaimStatus.CERTIFIED,
    SubcontractClaimStatus.PAID,
}


async def _measurement_allocated_quantity(
    db: AsyncSession,
    *,
    measurement_entry_id: UUID,
    exclude_claim_id: UUID | None = None,
) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(SubcontractClaimLine.certified_quantity), 0))
        .join(SubcontractClaim, SubcontractClaim.id == SubcontractClaimLine.claim_id)
        .where(
            SubcontractClaimLine.measurement_entry_id == measurement_entry_id,
            SubcontractClaim.status.in_(_CLOSED_CLAIM_STATUSES),
        )
    )
    if exclude_claim_id is not None:
        statement = statement.where(SubcontractClaimLine.claim_id != exclude_claim_id)
    allocated = await db.scalar(statement)
    return Decimal(allocated or 0)


async def _line_certified_quantity(
    db: AsyncSession,
    *,
    subcontract_line_id: UUID,
    exclude_claim_id: UUID | None = None,
) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(SubcontractClaimLine.certified_quantity), 0))
        .join(SubcontractClaim, SubcontractClaim.id == SubcontractClaimLine.claim_id)
        .where(
            SubcontractClaimLine.subcontract_line_id == subcontract_line_id,
            SubcontractClaim.status.in_(_CLOSED_CLAIM_STATUSES),
        )
    )
    if exclude_claim_id is not None:
        statement = statement.where(SubcontractClaimLine.claim_id != exclude_claim_id)
    certified = await db.scalar(statement)
    return Decimal(certified or 0)


async def _validate_measurement_allocation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    subcontract_line: SubcontractLine,
    measurement_entry_id: UUID,
    claimed_quantity: Decimal,
    lock_measurement: bool,
) -> None:
    statement = select(MeasurementEntry).where(
        MeasurementEntry.id == measurement_entry_id,
        MeasurementEntry.project_id == project_id,
        MeasurementEntry.organization_id == organization_id,
    )
    if lock_measurement:
        statement = statement.with_for_update()
    measurement = await db.scalar(statement)
    if measurement is None or measurement.status != MeasurementStatus.CERTIFIED:
        raise SubcontractValidationError("Linked measurement must be certified")
    if (
        subcontract_line.boq_item_id is not None
        and measurement.boq_item_id != subcontract_line.boq_item_id
    ):
        raise SubcontractValidationError("Measurement BOQ item does not match the work-order line")

    allocated = await _measurement_allocated_quantity(
        db,
        measurement_entry_id=measurement_entry_id,
        exclude_claim_id=claim_id,
    )
    if allocated + claimed_quantity > measurement.quantity:
        raise SubcontractValidationError(
            "Claim quantity exceeds the remaining linked certified measurement quantity"
        )


async def add_claim_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SubcontractClaimLine:
    measurement_entry_id = values.get("measurement_entry_id")
    subcontract_line_id = values.get("subcontract_line_id")
    claimed_quantity = Decimal(values.get("claimed_quantity") or 0)

    if isinstance(measurement_entry_id, UUID) and isinstance(subcontract_line_id, UUID):
        claim = await db.scalar(
            select(SubcontractClaim).where(
                SubcontractClaim.id == claim_id,
                SubcontractClaim.project_id == project_id,
                SubcontractClaim.organization_id == organization_id,
            )
        )
        if claim is None:
            raise SubcontractValidationError("Progress claim was not found")
        subcontract_line = await db.scalar(
            select(SubcontractLine).where(
                SubcontractLine.id == subcontract_line_id,
                SubcontractLine.subcontract_id == claim.subcontract_id,
                SubcontractLine.project_id == project_id,
                SubcontractLine.organization_id == organization_id,
            )
        )
        if subcontract_line is None:
            raise SubcontractValidationError("Work-order line was not found for this claim")
        await _validate_measurement_allocation(
            db,
            organization_id=organization_id,
            project_id=project_id,
            claim_id=claim_id,
            subcontract_line=subcontract_line,
            measurement_entry_id=measurement_entry_id,
            claimed_quantity=claimed_quantity,
            lock_measurement=False,
        )

    return await _add_claim_line(
        db,
        organization_id=organization_id,
        project_id=project_id,
        claim_id=claim_id,
        values=values,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def certify_claim(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    other_deductions: Decimal,
    tax_withheld_amount: Decimal,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    claim = await db.scalar(
        select(SubcontractClaim)
        .where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.organization_id == organization_id,
        )
        .with_for_update()
    )
    if claim is None:
        raise SubcontractValidationError("Progress claim was not found")
    if claim.status != SubcontractClaimStatus.SUBMITTED:
        raise SubcontractValidationError("Only submitted claims can be certified")

    lines = list(
        (
            await db.scalars(
                select(SubcontractClaimLine)
                .where(SubcontractClaimLine.claim_id == claim_id)
                .order_by(SubcontractClaimLine.id)
            )
        ).all()
    )
    subcontract_line_ids = {line.subcontract_line_id for line in lines}
    subcontract_lines = {
        row.id: row
        for row in (
            await db.scalars(
                select(SubcontractLine)
                .where(
                    SubcontractLine.id.in_(subcontract_line_ids),
                    SubcontractLine.project_id == project_id,
                    SubcontractLine.organization_id == organization_id,
                )
                .order_by(SubcontractLine.id)
                .with_for_update()
            )
        ).all()
    }

    current_by_line: dict[UUID, Decimal] = defaultdict(Decimal)
    current_by_measurement: dict[UUID, Decimal] = defaultdict(Decimal)
    measurement_line: dict[UUID, SubcontractLine] = {}
    for line in lines:
        contract_line = subcontract_lines.get(line.subcontract_line_id)
        if contract_line is None or contract_line.subcontract_id != claim.subcontract_id:
            raise SubcontractValidationError("Work-order line was not found for this claim")
        current_by_line[line.subcontract_line_id] += line.claimed_quantity
        if line.measurement_entry_id is not None:
            current_by_measurement[line.measurement_entry_id] += line.claimed_quantity
            existing_line = measurement_line.get(line.measurement_entry_id)
            if (
                existing_line is not None
                and existing_line.boq_item_id is not None
                and contract_line.boq_item_id is not None
                and existing_line.boq_item_id != contract_line.boq_item_id
            ):
                raise SubcontractValidationError(
                    "A certified measurement cannot be allocated across different BOQ items"
                )
            measurement_line[line.measurement_entry_id] = contract_line

    for subcontract_line_id, current_quantity in current_by_line.items():
        contract_line = subcontract_lines[subcontract_line_id]
        previously_certified = await _line_certified_quantity(
            db,
            subcontract_line_id=subcontract_line_id,
            exclude_claim_id=claim_id,
        )
        if previously_certified + current_quantity > contract_line.quantity:
            raise SubcontractValidationError(
                "Certification would exceed the remaining work-order line quantity"
            )

    for measurement_entry_id in sorted(current_by_measurement, key=str):
        await _validate_measurement_allocation(
            db,
            organization_id=organization_id,
            project_id=project_id,
            claim_id=claim_id,
            subcontract_line=measurement_line[measurement_entry_id],
            measurement_entry_id=measurement_entry_id,
            claimed_quantity=current_by_measurement[measurement_entry_id],
            lock_measurement=True,
        )

    return await _certify_claim(
        db,
        organization_id=organization_id,
        project_id=project_id,
        claim_id=claim_id,
        expected_revision=expected_revision,
        other_deductions=other_deductions,
        tax_withheld_amount=tax_withheld_amount,
        actor_user_id=actor_user_id,
        actor_membership_id=actor_membership_id,
        session_id=session_id,
        reason=reason,
    )
