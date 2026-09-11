from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.financials.models import FinancialProjectCounter
from app.modules.financials.payables_models import (
    VendorBill,
    VendorBillLine,
    VendorBillMatchStatus,
    VendorBillReceiptMatch,
    VendorBillStatus,
)
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseRequisitionLine,
)
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus


class VendorPayableValidationError(ValueError):
    pass


class VendorPayableConflictError(VendorPayableValidationError):
    pass


_ACTIVE_BILL_STATUSES = {
    VendorBillStatus.SUBMITTED,
    VendorBillStatus.APPROVED,
    VendorBillStatus.PARTIALLY_PAID,
    VendorBillStatus.PAID,
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _quantity(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    found = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if found is None:
        raise VendorPayableValidationError("An active project membership is required")


async def _next_bill_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> str:
    project = await db.scalar(
        select(Project)
        .where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
        .with_for_update()
    )
    if project is None:
        raise VendorPayableValidationError("Project was not found")
    counter = await db.scalar(
        select(FinancialProjectCounter)
        .where(
            FinancialProjectCounter.organization_id == organization_id,
            FinancialProjectCounter.project_id == project_id,
            FinancialProjectCounter.kind == "vendor_bill",
        )
        .with_for_update()
    )
    if counter is None:
        counter = FinancialProjectCounter(
            organization_id=organization_id,
            project_id=project_id,
            kind="vendor_bill",
            next_number=2,
        )
        db.add(counter)
        number = 1
    else:
        number = counter.next_number
        counter.next_number += 1
    await db.flush()
    return f"VB-{number:06d}"


async def _publish(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    bill: VendorBill,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.vendor_bill.changed",
        entity_type="vendor_bill",
        entity_id=bill.id,
        entity_version=bill.revision,
        required_permission_key="financials.payable.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"status": bill.status.value, "match_status": bill.match_status.value},
    )


async def create_vendor_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    values: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorBill:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    purchase_order_id = values.get("purchase_order_id")
    if not isinstance(purchase_order_id, UUID):
        raise VendorPayableValidationError("purchase_order_id is required")
    po = await db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.project_id == project_id,
        )
    )
    if po is None:
        raise VendorPayableValidationError("Purchase order was not found")
    if po.status not in {
        PurchaseOrderStatus.ISSUED,
        PurchaseOrderStatus.PART_RECEIVED,
        PurchaseOrderStatus.CLOSED,
    }:
        raise VendorPayableValidationError(
            "Vendor bill requires an issued or received purchase order"
        )
    supplier_invoice_number = str(values.get("supplier_invoice_number") or "").strip()
    if not supplier_invoice_number:
        raise VendorPayableValidationError("Supplier invoice number is required")
    duplicate = await db.scalar(
        select(VendorBill.id).where(
            VendorBill.organization_id == organization_id,
            VendorBill.supplier_party_id == po.supplier_party_id,
            func.lower(VendorBill.supplier_invoice_number) == supplier_invoice_number.lower(),
            VendorBill.status != VendorBillStatus.CANCELLED,
        )
    )
    if duplicate is not None:
        raise VendorPayableConflictError(
            "This supplier invoice number already exists for the supplier"
        )
    number = await _next_bill_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    row = VendorBill(
        organization_id=organization_id,
        project_id=project_id,
        bill_number=number,
        supplier_party_id=po.supplier_party_id,
        purchase_order_id=po.id,
        supplier_invoice_number=supplier_invoice_number,
        invoice_date=values["invoice_date"],
        due_date=values.get("due_date"),
        currency_code=po.currency_code,
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.vendor_bill.created",
        target_type="vendor_bill",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "project_id": str(project_id),
            "bill_number": row.bill_number,
            "supplier_party_id": str(row.supplier_party_id),
            "purchase_order_id": str(row.purchase_order_id),
            "supplier_invoice_number": row.supplier_invoice_number,
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        bill=row,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def _prior_billed_po_quantity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_line_id: UUID,
    exclude_bill_id: UUID,
) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(VendorBillLine.quantity), 0))
        .join(VendorBill, VendorBill.id == VendorBillLine.vendor_bill_id)
        .where(
            VendorBillLine.organization_id == organization_id,
            VendorBillLine.project_id == project_id,
            VendorBillLine.purchase_order_line_id == purchase_order_line_id,
            VendorBill.id != exclude_bill_id,
            VendorBill.status.in_(_ACTIVE_BILL_STATUSES),
        )
    )
    return _quantity(Decimal(value or 0))


async def _prior_matched_receipt_quantity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    goods_receipt_line_id: UUID,
    exclude_bill_id: UUID,
) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(VendorBillReceiptMatch.matched_quantity), 0))
        .join(
            VendorBillLine,
            VendorBillLine.id == VendorBillReceiptMatch.vendor_bill_line_id,
        )
        .join(VendorBill, VendorBill.id == VendorBillLine.vendor_bill_id)
        .where(
            VendorBillReceiptMatch.organization_id == organization_id,
            VendorBillReceiptMatch.project_id == project_id,
            VendorBillReceiptMatch.goods_receipt_line_id == goods_receipt_line_id,
            VendorBill.id != exclude_bill_id,
            VendorBill.status.in_(_ACTIVE_BILL_STATUSES),
        )
    )
    return _quantity(Decimal(value or 0))


async def _boq_item_for_po_line(
    db: AsyncSession,
    po_line: PurchaseOrderLine,
) -> UUID | None:
    if po_line.requisition_line_id is None:
        return None
    return await db.scalar(
        select(PurchaseRequisitionLine.boq_item_id).where(
            PurchaseRequisitionLine.id == po_line.requisition_line_id,
            PurchaseRequisitionLine.organization_id == po_line.organization_id,
            PurchaseRequisitionLine.project_id == po_line.project_id,
        )
    )


def _match_status(
    *,
    missing_receipt: bool,
    quantity_variance: Decimal,
    price_variance_amount: Decimal,
) -> VendorBillMatchStatus:
    if missing_receipt:
        return VendorBillMatchStatus.MISSING_RECEIPT
    has_quantity_variance = quantity_variance > 0
    has_price_variance = price_variance_amount != 0
    if has_quantity_variance and has_price_variance:
        return VendorBillMatchStatus.QUANTITY_AND_PRICE_VARIANCE
    if has_quantity_variance:
        return VendorBillMatchStatus.QUANTITY_VARIANCE
    if has_price_variance:
        return VendorBillMatchStatus.PRICE_VARIANCE
    return VendorBillMatchStatus.MATCHED


async def _evaluate_line(
    db: AsyncSession,
    *,
    bill: VendorBill,
    line: VendorBillLine,
    po_line: PurchaseOrderLine,
    receipt_matches: list[VendorBillReceiptMatch],
) -> None:
    price_variance = _money((line.unit_price - po_line.unit_price) * line.quantity)
    missing_receipt = False
    matched_quantity = Decimal(0)
    quantity_variance = Decimal(0)

    if po_line.material_id is not None:
        if not receipt_matches:
            missing_receipt = True
            quantity_variance = line.quantity
        else:
            seen: set[UUID] = set()
            valid_available = Decimal(0)
            requested_match = Decimal(0)
            for match in receipt_matches:
                if match.goods_receipt_line_id in seen:
                    raise VendorPayableValidationError(
                        "A GRN line can only be allocated once to the same vendor bill line"
                    )
                seen.add(match.goods_receipt_line_id)
                pair = await db.execute(
                    select(GoodsReceiptLine, GoodsReceipt)
                    .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id)
                    .where(
                        GoodsReceiptLine.id == match.goods_receipt_line_id,
                        GoodsReceiptLine.organization_id == bill.organization_id,
                        GoodsReceiptLine.project_id == bill.project_id,
                        GoodsReceiptLine.purchase_order_line_id == po_line.id,
                        GoodsReceipt.status == GoodsReceiptStatus.RECEIVED,
                    )
                )
                result = pair.first()
                if result is None:
                    raise VendorPayableValidationError(
                        "Receipt allocation must reference a received GRN line for the PO line"
                    )
                grn_line = result[0]
                prior = await _prior_matched_receipt_quantity(
                    db,
                    organization_id=bill.organization_id,
                    project_id=bill.project_id,
                    goods_receipt_line_id=grn_line.id,
                    exclude_bill_id=bill.id,
                )
                available = max(Decimal(0), grn_line.accepted_quantity - prior)
                requested_match += match.matched_quantity
                valid_available += min(match.matched_quantity, available)
            matched_quantity = min(line.quantity, valid_available, requested_match)
            quantity_variance = max(
                Decimal(0),
                line.quantity - matched_quantity,
                requested_match - valid_available,
            )
    else:
        if receipt_matches:
            raise VendorPayableValidationError(
                "Service PO lines must not allocate physical GRN quantities"
            )
        prior = await _prior_billed_po_quantity(
            db,
            organization_id=bill.organization_id,
            project_id=bill.project_id,
            purchase_order_line_id=po_line.id,
            exclude_bill_id=bill.id,
        )
        available = max(Decimal(0), po_line.quantity - prior)
        matched_quantity = min(line.quantity, available)
        quantity_variance = max(Decimal(0), line.quantity - available)

    line.matched_quantity = _quantity(matched_quantity)
    line.quantity_variance = _quantity(quantity_variance)
    line.price_variance_amount = price_variance
    line.match_status = _match_status(
        missing_receipt=missing_receipt,
        quantity_variance=line.quantity_variance,
        price_variance_amount=price_variance,
    )


async def _refresh_bill(
    db: AsyncSession,
    *,
    bill: VendorBill,
) -> list[VendorBillLine]:
    lines = list(
        (
            await db.scalars(
                select(VendorBillLine)
                .where(
                    VendorBillLine.organization_id == bill.organization_id,
                    VendorBillLine.project_id == bill.project_id,
                    VendorBillLine.vendor_bill_id == bill.id,
                )
                .order_by(VendorBillLine.line_number)
            )
        ).all()
    )
    subtotal = Decimal(0)
    tax_amount = Decimal(0)
    statuses: list[VendorBillMatchStatus] = []
    for line in lines:
        po_line = await db.scalar(
            select(PurchaseOrderLine).where(
                PurchaseOrderLine.id == line.purchase_order_line_id,
                PurchaseOrderLine.organization_id == bill.organization_id,
                PurchaseOrderLine.project_id == bill.project_id,
                PurchaseOrderLine.purchase_order_id == bill.purchase_order_id,
            )
        )
        if po_line is None:
            raise VendorPayableValidationError("Purchase order line was not found")
        matches = list(
            (
                await db.scalars(
                    select(VendorBillReceiptMatch).where(
                        VendorBillReceiptMatch.organization_id == bill.organization_id,
                        VendorBillReceiptMatch.project_id == bill.project_id,
                        VendorBillReceiptMatch.vendor_bill_line_id == line.id,
                    )
                )
            ).all()
        )
        await _evaluate_line(
            db,
            bill=bill,
            line=line,
            po_line=po_line,
            receipt_matches=matches,
        )
        subtotal += line.taxable_value
        tax_amount += line.tax_amount
        statuses.append(line.match_status)

    bill.subtotal = _money(subtotal)
    bill.tax_amount = _money(tax_amount)
    bill.total_amount = _money(bill.subtotal + bill.tax_amount)
    if not statuses:
        bill.match_status = VendorBillMatchStatus.UNCHECKED
    elif VendorBillMatchStatus.MISSING_RECEIPT in statuses:
        bill.match_status = VendorBillMatchStatus.MISSING_RECEIPT
    elif VendorBillMatchStatus.QUANTITY_AND_PRICE_VARIANCE in statuses:
        bill.match_status = VendorBillMatchStatus.QUANTITY_AND_PRICE_VARIANCE
    elif VendorBillMatchStatus.QUANTITY_VARIANCE in statuses and VendorBillMatchStatus.PRICE_VARIANCE in statuses:
        bill.match_status = VendorBillMatchStatus.QUANTITY_AND_PRICE_VARIANCE
    elif VendorBillMatchStatus.QUANTITY_VARIANCE in statuses:
        bill.match_status = VendorBillMatchStatus.QUANTITY_VARIANCE
    elif VendorBillMatchStatus.PRICE_VARIANCE in statuses:
        bill.match_status = VendorBillMatchStatus.PRICE_VARIANCE
    else:
        bill.match_status = VendorBillMatchStatus.MATCHED
    await db.flush()
    return lines


async def add_vendor_bill_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    values: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorBillLine:
    bill = await db.scalar(
        select(VendorBill)
        .where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == organization_id,
            VendorBill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise VendorPayableValidationError("Vendor bill was not found")
    if bill.status != VendorBillStatus.DRAFT:
        raise VendorPayableValidationError("Only draft vendor bills can be edited")
    po_line_id = values.get("purchase_order_line_id")
    if not isinstance(po_line_id, UUID):
        raise VendorPayableValidationError("purchase_order_line_id is required")
    po_line = await db.scalar(
        select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == po_line_id,
            PurchaseOrderLine.organization_id == organization_id,
            PurchaseOrderLine.project_id == project_id,
            PurchaseOrderLine.purchase_order_id == bill.purchase_order_id,
        )
    )
    if po_line is None:
        raise VendorPayableValidationError("Purchase order line was not found for this bill")
    duplicate = await db.scalar(
        select(VendorBillLine.id).where(
            VendorBillLine.vendor_bill_id == bill.id,
            VendorBillLine.purchase_order_line_id == po_line.id,
        )
    )
    if duplicate is not None:
        raise VendorPayableConflictError(
            "The purchase order line is already represented on this vendor bill"
        )
    quantity = _quantity(Decimal(values.get("quantity") or 0))
    unit_price = Decimal(values.get("unit_price") or 0).quantize(Decimal("0.0001"))
    tax_amount = _money(Decimal(values.get("tax_amount") or 0))
    if quantity <= 0:
        raise VendorPayableValidationError("Vendor bill quantity must be greater than zero")
    if unit_price < 0 or tax_amount < 0:
        raise VendorPayableValidationError("Vendor bill amounts cannot be negative")
    max_line = await db.scalar(
        select(func.coalesce(func.max(VendorBillLine.line_number), 0)).where(
            VendorBillLine.vendor_bill_id == bill.id
        )
    )
    line = VendorBillLine(
        organization_id=organization_id,
        project_id=project_id,
        vendor_bill_id=bill.id,
        line_number=int(max_line or 0) + 1,
        purchase_order_line_id=po_line.id,
        material_id=po_line.material_id,
        wbs_code_id=po_line.wbs_code_id,
        boq_item_id=await _boq_item_for_po_line(db, po_line),
        description=po_line.description,
        unit_code=po_line.unit_code,
        quantity=quantity,
        unit_price=unit_price,
        po_unit_price_snapshot=po_line.unit_price,
        taxable_value=_money(quantity * unit_price),
        hsn_sac=(values.get("hsn_sac") if isinstance(values.get("hsn_sac"), str) else None)
        or po_line.hsn_sac,
        tax_code=(values.get("tax_code") if isinstance(values.get("tax_code"), str) else None)
        or po_line.tax_code,
        tax_rate=(Decimal(values["tax_rate"]) if values.get("tax_rate") is not None else po_line.tax_rate),
        tax_amount=tax_amount,
        line_total=_money(quantity * unit_price + tax_amount),
    )
    db.add(line)
    await db.flush()

    raw_matches = values.get("receipt_matches") or []
    if not isinstance(raw_matches, list):
        raise VendorPayableValidationError("receipt_matches must be a list")
    for raw in raw_matches:
        if not isinstance(raw, dict):
            raise VendorPayableValidationError("Invalid receipt allocation")
        receipt_line_id = raw.get("goods_receipt_line_id")
        matched_quantity = _quantity(Decimal(raw.get("matched_quantity") or 0))
        if not isinstance(receipt_line_id, UUID) or matched_quantity <= 0:
            raise VendorPayableValidationError("Receipt allocation requires a GRN line and quantity")
        db.add(
            VendorBillReceiptMatch(
                organization_id=organization_id,
                project_id=project_id,
                vendor_bill_line_id=line.id,
                goods_receipt_line_id=receipt_line_id,
                matched_quantity=matched_quantity,
            )
        )
    await db.flush()
    matches = list(
        (
            await db.scalars(
                select(VendorBillReceiptMatch).where(
                    VendorBillReceiptMatch.vendor_bill_line_id == line.id
                )
            )
        ).all()
    )
    await _evaluate_line(
        db,
        bill=bill,
        line=line,
        po_line=po_line,
        receipt_matches=matches,
    )
    bill.revision += 1
    await _refresh_bill(db, bill=bill)
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.vendor_bill_line.created",
        target_type="vendor_bill_line",
        target_id=str(line.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "vendor_bill_id": str(bill.id),
            "purchase_order_line_id": str(po_line.id),
            "quantity": line.quantity,
            "line_total": line.line_total,
            "match_status": line.match_status.value,
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        bill=bill,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return line


async def delete_vendor_bill_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    line_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorBill:
    bill = await db.scalar(
        select(VendorBill)
        .where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == organization_id,
            VendorBill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise VendorPayableValidationError("Vendor bill was not found")
    if bill.status != VendorBillStatus.DRAFT:
        raise VendorPayableValidationError("Only draft vendor bills can be edited")
    line = await db.scalar(
        select(VendorBillLine).where(
            VendorBillLine.id == line_id,
            VendorBillLine.vendor_bill_id == bill.id,
            VendorBillLine.organization_id == organization_id,
            VendorBillLine.project_id == project_id,
        )
    )
    if line is None:
        raise VendorPayableValidationError("Vendor bill line was not found")
    await db.delete(line)
    bill.revision += 1
    await db.flush()
    await _refresh_bill(db, bill=bill)
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.vendor_bill_line.deleted",
        target_type="vendor_bill_line",
        target_id=str(line_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"vendor_bill_id": str(bill.id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        bill=bill,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return bill


async def submit_vendor_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    allow_variance_override: bool,
    reason: str | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorBill:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    bill = await db.scalar(
        select(VendorBill)
        .where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == organization_id,
            VendorBill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise VendorPayableValidationError("Vendor bill was not found")
    if bill.revision != expected_revision:
        raise VendorPayableConflictError("Vendor bill changed; refresh before continuing")
    if bill.status not in {VendorBillStatus.DRAFT, VendorBillStatus.REJECTED}:
        raise VendorPayableValidationError("Only draft or rejected vendor bills can be submitted")
    lines = await _refresh_bill(db, bill=bill)
    if not lines:
        raise VendorPayableValidationError("Vendor bill must contain at least one line")
    has_variance = bill.match_status != VendorBillMatchStatus.MATCHED
    if has_variance and not allow_variance_override:
        raise VendorPayableValidationError(
            f"Vendor bill cannot be submitted while match status is {bill.match_status.value}"
        )
    if has_variance:
        normalized_reason = (reason or "").strip()
        if not normalized_reason:
            raise VendorPayableValidationError("Variance override requires a reason")
        bill.variance_override_by_membership_id = membership_id
        bill.variance_override_reason = normalized_reason
    else:
        bill.variance_override_by_membership_id = None
        bill.variance_override_reason = None
    bill.status = VendorBillStatus.SUBMITTED
    bill.submitted_by_membership_id = membership_id
    bill.submitted_at = datetime.now(UTC)
    bill.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.vendor_bill.submitted",
        target_type="vendor_bill",
        target_id=str(bill.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if has_variance else AuditRisk.HIGH,
        reason=reason,
        changes={
            "status": bill.status.value,
            "match_status": bill.match_status.value,
            "total_amount": bill.total_amount,
            "variance_override": has_variance,
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        bill=bill,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return bill


async def approve_vendor_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    reason: str | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorBill:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    bill = await db.scalar(
        select(VendorBill)
        .where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == organization_id,
            VendorBill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise VendorPayableValidationError("Vendor bill was not found")
    if bill.revision != expected_revision:
        raise VendorPayableConflictError("Vendor bill changed; refresh before continuing")
    if bill.status != VendorBillStatus.SUBMITTED:
        raise VendorPayableValidationError("Only submitted vendor bills can be approved")
    await _refresh_bill(db, bill=bill)
    if (
        bill.match_status != VendorBillMatchStatus.MATCHED
        and bill.variance_override_by_membership_id is None
    ):
        raise VendorPayableValidationError(
            "Vendor bill match changed after submission and requires variance review"
        )
    bill.status = VendorBillStatus.APPROVED
    bill.approved_by_membership_id = membership_id
    bill.approved_at = datetime.now(UTC)
    bill.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.vendor_bill.approved",
        target_type="vendor_bill",
        target_id=str(bill.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "status": bill.status.value,
            "match_status": bill.match_status.value,
            "total_amount": bill.total_amount,
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        bill=bill,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return bill


async def reject_vendor_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    reason: str | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorBill:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    bill = await db.scalar(
        select(VendorBill)
        .where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == organization_id,
            VendorBill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise VendorPayableValidationError("Vendor bill was not found")
    if bill.revision != expected_revision:
        raise VendorPayableConflictError("Vendor bill changed; refresh before continuing")
    if bill.status != VendorBillStatus.SUBMITTED:
        raise VendorPayableValidationError("Only submitted vendor bills can be rejected")
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise VendorPayableValidationError("Rejection requires a reason")
    bill.status = VendorBillStatus.REJECTED
    bill.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.vendor_bill.rejected",
        target_type="vendor_bill",
        target_id=str(bill.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=normalized_reason,
        changes={"status": bill.status.value, "revision": bill.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        bill=bill,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return bill
