from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.measurement_control_schemas import (
    BOQMeasurementControlLine,
    BOQMeasurementControlSummary,
)
from app.modules.commercial.models import (
    BOQ,
    BOQItem,
    BOQStatus,
    MeasurementEntry,
    MeasurementStatus,
    RABill,
    RABillLine,
    RABillStatus,
)
from app.modules.commercial.service import CommercialValidationError, _require_project


ZERO = Decimal("0.00")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def build_boq_measurement_control(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> BOQMeasurementControlSummary:
    project = await _require_project(db, organization_id, project_id)
    currency_code = (project.currency_code or "INR").upper()

    items = list(
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
    if not items:
        raise CommercialValidationError(
            "Project has no approved BOQ in the project currency for measurement control"
        )

    measurement_rows = await db.execute(
        select(
            MeasurementEntry.boq_item_id,
            MeasurementEntry.status,
            func.coalesce(func.sum(MeasurementEntry.quantity), 0),
        )
        .where(
            MeasurementEntry.organization_id == organization_id,
            MeasurementEntry.project_id == project_id,
        )
        .group_by(MeasurementEntry.boq_item_id, MeasurementEntry.status)
    )
    measurement_totals: dict[UUID, dict[MeasurementStatus, Decimal]] = {}
    for boq_item_id, measurement_status, quantity in measurement_rows.all():
        measurement_totals.setdefault(boq_item_id, {})[measurement_status] = Decimal(quantity)

    foreign_bill_count = int(
        await db.scalar(
            select(func.count(RABill.id)).where(
                RABill.organization_id == organization_id,
                RABill.project_id == project_id,
                RABill.status != RABillStatus.CANCELLED,
                RABill.currency_code != currency_code,
            )
        )
        or 0
    )
    if foreign_bill_count:
        raise CommercialValidationError(
            "Measurement control cannot combine RA bills in different currencies"
        )

    bill_rows = await db.execute(
        select(
            RABillLine.boq_item_id,
            RABill.status,
            func.coalesce(func.sum(RABillLine.current_quantity), 0),
            func.coalesce(func.sum(RABillLine.gross_amount), 0),
        )
        .join(RABill, RABill.id == RABillLine.ra_bill_id)
        .where(
            RABillLine.organization_id == organization_id,
            RABillLine.project_id == project_id,
            RABill.status.in_(
                {RABillStatus.SUBMITTED, RABillStatus.CERTIFIED, RABillStatus.PAID}
            ),
            RABill.currency_code == currency_code,
        )
        .group_by(RABillLine.boq_item_id, RABill.status)
    )
    billed_quantities: dict[UUID, Decimal] = {}
    billed_values: dict[UUID, Decimal] = {}
    paid_quantities: dict[UUID, Decimal] = {}
    paid_values: dict[UUID, Decimal] = {}
    for boq_item_id, bill_status, quantity, amount in bill_rows.all():
        billed_quantities[boq_item_id] = billed_quantities.get(boq_item_id, Decimal(0)) + Decimal(
            quantity
        )
        billed_values[boq_item_id] = billed_values.get(boq_item_id, Decimal(0)) + Decimal(amount)
        if bill_status == RABillStatus.PAID:
            paid_quantities[boq_item_id] = paid_quantities.get(boq_item_id, Decimal(0)) + Decimal(
                quantity
            )
            paid_values[boq_item_id] = paid_values.get(boq_item_id, Decimal(0)) + Decimal(amount)

    lines: list[BOQMeasurementControlLine] = []
    for item in items:
        totals = measurement_totals.get(item.id, {})
        draft_quantity = totals.get(MeasurementStatus.DRAFT, Decimal(0))
        submitted_only = totals.get(MeasurementStatus.SUBMITTED, Decimal(0))
        certified_quantity = totals.get(MeasurementStatus.CERTIFIED, Decimal(0))
        measured_quantity = draft_quantity + submitted_only + certified_quantity
        submitted_quantity = submitted_only + certified_quantity
        billed_quantity = billed_quantities.get(item.id, Decimal(0))
        paid_quantity = paid_quantities.get(item.id, Decimal(0))
        billed_value = _money(billed_values.get(item.id, Decimal(0)))
        paid_value = _money(paid_values.get(item.id, Decimal(0)))
        certified_value = _money(certified_quantity * Decimal(item.rate))
        boq_quantity = Decimal(item.quantity)
        lines.append(
            BOQMeasurementControlLine(
                boq_item_id=item.id,
                boq_id=item.boq_id,
                wbs_code_id=item.wbs_code_id,
                line_number=item.line_number,
                item_code=item.item_code,
                description=item.description,
                unit_code=item.unit_code,
                boq_quantity=boq_quantity,
                boq_rate=item.rate,
                boq_amount=_money(Decimal(item.amount)),
                measured_quantity=measured_quantity,
                submitted_quantity=submitted_quantity,
                certified_quantity=certified_quantity,
                billed_quantity=billed_quantity,
                paid_quantity=paid_quantity,
                certified_value=certified_value,
                billed_value=billed_value,
                paid_value=paid_value,
                remaining_to_certify=boq_quantity - certified_quantity,
                remaining_to_bill=boq_quantity - billed_quantity,
            )
        )

    return BOQMeasurementControlSummary(
        project_id=project_id,
        currency_code=currency_code,
        total_boq_value=_money(sum((line.boq_amount for line in lines), ZERO)),
        total_certified_value=_money(sum((line.certified_value for line in lines), ZERO)),
        total_billed_value=_money(sum((line.billed_value for line in lines), ZERO)),
        total_paid_value=_money(sum((line.paid_value for line in lines), ZERO)),
        lines=lines,
    )
