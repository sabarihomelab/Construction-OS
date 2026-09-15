from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQItem, Party, PartyStatus, WBSCode
from app.modules.equipment.models import Material
from app.modules.events.service import enqueue_event
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RequisitionStatus,
)
from app.modules.procurement.numbering import allocate_procurement_number
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.search.service import schedule_search_index


class ProcurementValidationError(ValueError):
    pass


class ProcurementConflictError(ValueError):
    pass


MONEY = Decimal("0.01")
HUNDRED = Decimal(100)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    exists = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if exists is None:
        raise ProcurementValidationError("Project was not found")


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    exists = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if exists is None:
        raise ProcurementValidationError("User must be an active member of this project")


async def _publish(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    entity_version: int,
    permission: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key=permission,
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": entity_version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
    )


async def _validate_line_refs(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    material_id: UUID | None,
    wbs_code_id: UUID | None,
    boq_item_id: UUID | None,
) -> None:
    if material_id is not None:
        material = await db.scalar(
            select(Material.id).where(
                Material.id == material_id,
                Material.organization_id == organization_id,
            )
        )
        if material is None:
            raise ProcurementValidationError("Material was not found in this company")
    if wbs_code_id is not None:
        wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_code_id,
                WBSCode.project_id == project_id,
                WBSCode.organization_id == organization_id,
            )
        )
        if wbs is None:
            raise ProcurementValidationError("WBS code was not found in this project")
    if boq_item_id is not None:
        boq = await db.scalar(
            select(BOQItem.id).where(
                BOQItem.id == boq_item_id,
                BOQItem.project_id == project_id,
                BOQItem.organization_id == organization_id,
            )
        )
        if boq is None:
            raise ProcurementValidationError("BOQ item was not found in this project")


async def create_requisition(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    requested_by_membership_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseRequisition:
    await _require_project(db, organization_id, project_id)
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=requested_by_membership_id,
    )
    title = str(values.get("title") or "").strip()
    if not title:
        raise ProcurementValidationError("Requisition title is required")
    number = await allocate_procurement_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="requisition",
    )
    row = PurchaseRequisition(
        organization_id=organization_id,
        project_id=project_id,
        number=f"PR-{number:05d}",
        title=title,
        requested_by_membership_id=requested_by_membership_id,
        required_by=values.get("required_by"),
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.requisition.created",
        target_type="purchase_requisition",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"number": row.number, "project_id": str(project_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.requisition.created",
        entity_type="purchase_requisition",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.requisition.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def add_requisition_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    requisition_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseRequisitionLine:
    requisition = await db.scalar(
        select(PurchaseRequisition)
        .where(
            PurchaseRequisition.id == requisition_id,
            PurchaseRequisition.project_id == project_id,
            PurchaseRequisition.organization_id == organization_id,
        )
        .with_for_update()
    )
    if requisition is None:
        raise ProcurementValidationError("Requisition was not found")
    if requisition.status != RequisitionStatus.DRAFT:
        raise ProcurementValidationError("Only draft requisitions can be edited")
    data = dict(values)
    await _validate_line_refs(
        db,
        organization_id=organization_id,
        project_id=project_id,
        material_id=data.get("material_id") if isinstance(data.get("material_id"), UUID) else None,
        wbs_code_id=data.get("wbs_code_id") if isinstance(data.get("wbs_code_id"), UUID) else None,
        boq_item_id=data.get("boq_item_id") if isinstance(data.get("boq_item_id"), UUID) else None,
    )
    quantity = Decimal(data.get("quantity") or 0)
    rate = money(Decimal(data.get("estimated_unit_rate") or 0))
    data["quantity"] = quantity
    data["estimated_unit_rate"] = rate
    data["estimated_amount"] = money(quantity * rate)
    line = PurchaseRequisitionLine(
        organization_id=organization_id,
        project_id=project_id,
        requisition_id=requisition_id,
        **data,
    )
    db.add(line)
    requisition.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.requisition_line.created",
        target_type="purchase_requisition_line",
        target_id=str(line.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"requisition_id": str(requisition_id), "amount": str(line.estimated_amount)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.requisition.updated",
        entity_type="purchase_requisition",
        entity_id=requisition.id,
        entity_version=requisition.revision,
        permission="procurement.requisition.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return line


async def transition_requisition(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    requisition_id: UUID,
    expected_revision: int,
    target: RequisitionStatus,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> PurchaseRequisition:
    row = await db.scalar(
        select(PurchaseRequisition)
        .where(
            PurchaseRequisition.id == requisition_id,
            PurchaseRequisition.project_id == project_id,
            PurchaseRequisition.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ProcurementValidationError("Requisition was not found")
    if row.revision != expected_revision:
        raise ProcurementConflictError("Requisition changed; refresh before continuing")
    allowed = {
        RequisitionStatus.DRAFT: {RequisitionStatus.SUBMITTED, RequisitionStatus.CANCELLED},
        RequisitionStatus.SUBMITTED: {RequisitionStatus.APPROVED, RequisitionStatus.REJECTED},
        RequisitionStatus.REJECTED: {RequisitionStatus.DRAFT, RequisitionStatus.CANCELLED},
    }
    if target not in allowed.get(row.status, set()):
        raise ProcurementValidationError(
            f"Requisition cannot move from {row.status.value} to {target.value}"
        )
    if target == RequisitionStatus.SUBMITTED:
        count = await db.scalar(
            select(func.count(PurchaseRequisitionLine.id)).where(
                PurchaseRequisitionLine.requisition_id == row.id
            )
        )
        if not count:
            raise ProcurementValidationError("A requisition with no lines cannot be submitted")
        row.submitted_at = datetime.now(UTC)
    if target == RequisitionStatus.APPROVED:
        await _require_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=actor_membership_id,
        )
        row.approved_by_membership_id = actor_membership_id
        row.approved_at = datetime.now(UTC)
    row.status = target
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"procurement.requisition.{target.value}",
        target_type="purchase_requisition",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if target == RequisitionStatus.APPROVED else AuditRisk.HIGH,
        reason=reason,
        changes={"status": target.value, "revision": row.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"procurement.requisition.{target.value}",
        entity_type="purchase_requisition",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.requisition.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def create_purchase_order(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseOrder:
    await _require_project(db, organization_id, project_id)
    supplier_id = values.get("supplier_party_id")
    if not isinstance(supplier_id, UUID):
        raise ProcurementValidationError("Supplier is required")
    supplier = await db.scalar(
        select(Party).where(Party.id == supplier_id, Party.organization_id == organization_id)
    )
    if supplier is None or supplier.status != PartyStatus.ACTIVE:
        raise ProcurementValidationError("Active supplier was not found")
    requisition_id = values.get("requisition_id")
    if isinstance(requisition_id, UUID):
        requisition = await db.scalar(
            select(PurchaseRequisition).where(
                PurchaseRequisition.id == requisition_id,
                PurchaseRequisition.project_id == project_id,
                PurchaseRequisition.organization_id == organization_id,
            )
        )
        if requisition is None or requisition.status != RequisitionStatus.APPROVED:
            raise ProcurementValidationError("Purchase order requires an approved requisition")
    number = await allocate_procurement_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="po",
    )
    row = PurchaseOrder(
        organization_id=organization_id,
        project_id=project_id,
        number=f"PO-{number:05d}",
        supplier_party_id=supplier_id,
        requisition_id=requisition_id if isinstance(requisition_id, UUID) else None,
        order_date=values["order_date"],
        expected_delivery_date=values.get("expected_delivery_date"),
        currency_code=str(values.get("currency_code") or "INR").upper(),
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.purchase_order.created",
        target_type="purchase_order",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"number": row.number, "supplier_party_id": str(supplier_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.purchase_order.created",
        entity_type="purchase_order",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def _recalculate_po(db: AsyncSession, po: PurchaseOrder) -> None:
    totals = await db.execute(
        select(
            func.coalesce(func.sum(PurchaseOrderLine.taxable_value), 0),
            func.coalesce(func.sum(PurchaseOrderLine.tax_amount), 0),
            func.coalesce(func.sum(PurchaseOrderLine.line_total), 0),
        ).where(PurchaseOrderLine.purchase_order_id == po.id)
    )
    subtotal, tax_total, total = totals.one()
    po.subtotal = money(Decimal(subtotal))
    po.tax_total = money(Decimal(tax_total))
    po.total = money(Decimal(total))


async def add_purchase_order_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseOrderLine:
    po = await db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.project_id == project_id,
            PurchaseOrder.organization_id == organization_id,
        )
        .with_for_update()
    )
    if po is None:
        raise ProcurementValidationError("Purchase order was not found")
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ProcurementValidationError("Only draft purchase orders can be edited")
    data = dict(values)
    await _validate_line_refs(
        db,
        organization_id=organization_id,
        project_id=project_id,
        material_id=data.get("material_id") if isinstance(data.get("material_id"), UUID) else None,
        wbs_code_id=data.get("wbs_code_id") if isinstance(data.get("wbs_code_id"), UUID) else None,
        boq_item_id=None,
    )
    req_line_id = data.get("requisition_line_id")
    if isinstance(req_line_id, UUID):
        req_line = await db.scalar(
            select(PurchaseRequisitionLine).where(
                PurchaseRequisitionLine.id == req_line_id,
                PurchaseRequisitionLine.project_id == project_id,
                PurchaseRequisitionLine.organization_id == organization_id,
            )
        )
        if req_line is None:
            raise ProcurementValidationError("Requisition line was not found in this project")
    quantity = Decimal(data.get("quantity") or 0)
    unit_price = money(Decimal(data.get("unit_price") or 0))
    taxable = money(quantity * unit_price)
    tax_rate_raw = data.get("tax_rate")
    tax_rate = Decimal(tax_rate_raw) if tax_rate_raw is not None else None
    tax_amount = money(taxable * tax_rate / HUNDRED) if tax_rate is not None else Decimal(0)
    data["quantity"] = quantity
    data["unit_price"] = unit_price
    data["taxable_value"] = taxable
    data["tax_rate"] = tax_rate
    data["tax_amount"] = tax_amount
    data["line_total"] = money(taxable + tax_amount)
    line = PurchaseOrderLine(
        organization_id=organization_id,
        project_id=project_id,
        purchase_order_id=purchase_order_id,
        **data,
    )
    db.add(line)
    await db.flush()
    await _recalculate_po(db, po)
    po.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.purchase_order_line.created",
        target_type="purchase_order_line",
        target_id=str(line.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"purchase_order_id": str(po.id), "line_total": str(line.line_total)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.purchase_order.updated",
        entity_type="purchase_order",
        entity_id=po.id,
        entity_version=po.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return line


async def transition_purchase_order(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_id: UUID,
    expected_revision: int,
    target: PurchaseOrderStatus,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> PurchaseOrder:
    row = await db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.project_id == project_id,
            PurchaseOrder.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ProcurementValidationError("Purchase order was not found")
    if row.revision != expected_revision:
        raise ProcurementConflictError("Purchase order changed; refresh before continuing")
    allowed = {
        PurchaseOrderStatus.DRAFT: {PurchaseOrderStatus.SUBMITTED, PurchaseOrderStatus.CANCELLED},
        PurchaseOrderStatus.SUBMITTED: {PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.DRAFT},
        PurchaseOrderStatus.APPROVED: {PurchaseOrderStatus.ISSUED, PurchaseOrderStatus.CANCELLED},
    }
    if target not in allowed.get(row.status, set()):
        raise ProcurementValidationError(
            f"Purchase order cannot move from {row.status.value} to {target.value}"
        )
    if target == PurchaseOrderStatus.SUBMITTED:
        count = await db.scalar(
            select(func.count(PurchaseOrderLine.id)).where(PurchaseOrderLine.purchase_order_id == row.id)
        )
        if not count:
            raise ProcurementValidationError("A purchase order with no lines cannot be submitted")
    if target == PurchaseOrderStatus.APPROVED:
        await _require_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=actor_membership_id,
        )
        row.approved_by_membership_id = actor_membership_id
        row.approved_at = datetime.now(UTC)
    if target == PurchaseOrderStatus.ISSUED:
        row.issued_at = datetime.now(UTC)
        if row.requisition_id is not None:
            requisition = await db.scalar(
                select(PurchaseRequisition)
                .where(PurchaseRequisition.id == row.requisition_id)
                .with_for_update()
            )
            if requisition is not None and requisition.status == RequisitionStatus.APPROVED:
                requisition.status = RequisitionStatus.CONVERTED
                requisition.revision += 1
    row.status = target
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"procurement.purchase_order.{target.value}",
        target_type="purchase_order",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if target in {PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.ISSUED} else AuditRisk.HIGH,
        reason=reason,
        changes={"status": target.value, "revision": row.revision, "total": str(row.total)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"procurement.purchase_order.{target.value}",
        entity_type="purchase_order",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def create_goods_receipt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    received_by_membership_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> GoodsReceipt:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=received_by_membership_id,
    )
    po_id = values.get("purchase_order_id")
    if not isinstance(po_id, UUID):
        raise ProcurementValidationError("Purchase order is required")
    po = await db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.project_id == project_id,
            PurchaseOrder.organization_id == organization_id,
        )
    )
    if po is None or po.status not in {
        PurchaseOrderStatus.ISSUED,
        PurchaseOrderStatus.PART_RECEIVED,
    }:
        raise ProcurementValidationError("Goods receipt requires an issued purchase order")
    number = await allocate_procurement_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="grn",
    )
    row = GoodsReceipt(
        organization_id=organization_id,
        project_id=project_id,
        purchase_order_id=po_id,
        number=f"GRN-{number:05d}",
        received_at=values["received_at"],
        received_by_membership_id=received_by_membership_id,
        challan_number=values.get("challan_number"),
        supplier_invoice_number=values.get("supplier_invoice_number"),
        delivered_by=values.get("delivered_by"),
        notes=values.get("notes"),
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.goods_receipt.created",
        target_type="goods_receipt",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"number": row.number, "purchase_order_id": str(po_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.goods_receipt.created",
        entity_type="goods_receipt",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.receipt.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def add_goods_receipt_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    goods_receipt_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> GoodsReceiptLine:
    receipt = await db.scalar(
        select(GoodsReceipt)
        .where(
            GoodsReceipt.id == goods_receipt_id,
            GoodsReceipt.project_id == project_id,
            GoodsReceipt.organization_id == organization_id,
        )
        .with_for_update()
    )
    if receipt is None:
        raise ProcurementValidationError("Goods receipt was not found")
    if receipt.status != GoodsReceiptStatus.DRAFT:
        raise ProcurementValidationError("Only draft goods receipts can be edited")
    po_line_id = values.get("purchase_order_line_id")
    if not isinstance(po_line_id, UUID):
        raise ProcurementValidationError("Purchase order line is required")
    po_line = await db.scalar(
        select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == po_line_id,
            PurchaseOrderLine.purchase_order_id == receipt.purchase_order_id,
            PurchaseOrderLine.project_id == project_id,
            PurchaseOrderLine.organization_id == organization_id,
        )
    )
    if po_line is None:
        raise ProcurementValidationError("Purchase order line was not found for this order")
    received = Decimal(values.get("received_quantity") or 0)
    accepted = Decimal(values.get("accepted_quantity") or 0)
    rejected = Decimal(values.get("rejected_quantity") or 0)
    if accepted + rejected > received:
        raise ProcurementValidationError("Accepted plus rejected quantity cannot exceed received quantity")
    prior = await db.scalar(
        select(func.coalesce(func.sum(GoodsReceiptLine.received_quantity), 0))
        .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id)
        .where(
            GoodsReceiptLine.purchase_order_line_id == po_line_id,
            GoodsReceipt.status == GoodsReceiptStatus.RECEIVED,
        )
    )
    if Decimal(prior or 0) + received > po_line.quantity:
        raise ProcurementValidationError("Receipt quantity exceeds the remaining purchase order quantity")
    row = GoodsReceiptLine(
        organization_id=organization_id,
        project_id=project_id,
        goods_receipt_id=goods_receipt_id,
        purchase_order_line_id=po_line_id,
        received_quantity=received,
        accepted_quantity=accepted,
        rejected_quantity=rejected,
        unit_code=str(values.get("unit_code") or po_line.unit_code),
        remarks=values.get("remarks") if isinstance(values.get("remarks"), str) else None,
    )
    db.add(row)
    receipt.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.goods_receipt_line.created",
        target_type="goods_receipt_line",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"goods_receipt_id": str(receipt.id), "received_quantity": str(received)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.goods_receipt.updated",
        entity_type="goods_receipt",
        entity_id=receipt.id,
        entity_version=receipt.revision,
        permission="procurement.receipt.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def receive_goods_receipt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    goods_receipt_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> GoodsReceipt:
    receipt = await db.scalar(
        select(GoodsReceipt)
        .where(
            GoodsReceipt.id == goods_receipt_id,
            GoodsReceipt.project_id == project_id,
            GoodsReceipt.organization_id == organization_id,
        )
        .with_for_update()
    )
    if receipt is None:
        raise ProcurementValidationError("Goods receipt was not found")
    if receipt.revision != expected_revision:
        raise ProcurementConflictError("Goods receipt changed; refresh before receiving")
    if receipt.status != GoodsReceiptStatus.DRAFT:
        raise ProcurementValidationError("Only draft goods receipts can be received")
    line_count = await db.scalar(
        select(func.count(GoodsReceiptLine.id)).where(GoodsReceiptLine.goods_receipt_id == receipt.id)
    )
    if not line_count:
        raise ProcurementValidationError("Goods receipt must contain at least one line")
    receipt.status = GoodsReceiptStatus.RECEIVED
    receipt.revision += 1
    await db.flush()

    po = await db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == receipt.purchase_order_id)
        .with_for_update()
    )
    if po is not None:
        po_lines = list(
            (
                await db.scalars(
                    select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id)
                )
            ).all()
        )
        all_complete = True
        for po_line in po_lines:
            accepted_total = await db.scalar(
                select(func.coalesce(func.sum(GoodsReceiptLine.accepted_quantity), 0))
                .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id)
                .where(
                    GoodsReceiptLine.purchase_order_line_id == po_line.id,
                    GoodsReceipt.status == GoodsReceiptStatus.RECEIVED,
                )
            )
            if Decimal(accepted_total or 0) < po_line.quantity:
                all_complete = False
                break
        po.status = PurchaseOrderStatus.CLOSED if all_complete else PurchaseOrderStatus.PART_RECEIVED
        po.revision += 1

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.goods_receipt.received",
        target_type="goods_receipt",
        target_id=str(receipt.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"status": receipt.status.value, "revision": receipt.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.goods_receipt.received",
        entity_type="goods_receipt",
        entity_id=receipt.id,
        entity_version=receipt.revision,
        permission="procurement.receipt.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return receipt
