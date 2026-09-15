from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.equipment.inventory_models import (
    MaterialStockLocation,
    MaterialStockTransaction,
    StockDirection,
    StockLocationStatus,
    StockSourceType,
    StockTransactionType,
)
from app.modules.equipment.models import Material
from app.modules.events.service import enqueue_event
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisitionLine,
)
from app.modules.projects.models import ProjectMembership, ProjectMembershipStatus


class InventoryValidationError(ValueError):
    pass


class InventoryConflictError(InventoryValidationError):
    pass


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
        raise InventoryValidationError("An active project membership is required")


async def require_stock_location(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    stock_location_id: UUID,
    lock: bool = False,
) -> MaterialStockLocation:
    statement = select(MaterialStockLocation).where(
        MaterialStockLocation.id == stock_location_id,
        MaterialStockLocation.organization_id == organization_id,
        MaterialStockLocation.project_id == project_id,
    )
    if lock:
        statement = statement.with_for_update()
    location = await db.scalar(statement)
    if location is None:
        raise InventoryValidationError("Stock location was not found in this project")
    if location.status != StockLocationStatus.ACTIVE:
        raise InventoryValidationError("Stock location is inactive")
    return location


async def create_stock_location(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> MaterialStockLocation:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    code = str(values.get("code") or "").strip()
    name = str(values.get("name") or "").strip()
    if not code or not name:
        raise InventoryValidationError("Stock location code and name are required")
    duplicate = await db.scalar(
        select(MaterialStockLocation.id).where(
            MaterialStockLocation.project_id == project_id,
            MaterialStockLocation.organization_id == organization_id,
            func.lower(MaterialStockLocation.code) == code.lower(),
        )
    )
    if duplicate is not None:
        raise InventoryConflictError("Stock location code already exists in this project")

    payload = dict(values)
    payload["code"] = code
    payload["name"] = name
    description = payload.get("description")
    payload["description"] = str(description).strip() or None if description is not None else None
    row = MaterialStockLocation(
        organization_id=organization_id,
        project_id=project_id,
        status=StockLocationStatus.ACTIVE,
        revision=1,
        **payload,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.inventory.location.created",
        target_type="material_stock_location",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "project_id": str(project_id),
            "code": row.code,
            "name": row.name,
            "location_type": row.location_type.value,
        },
    )
    return row


async def stock_quantity_on_hand(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    stock_location_id: UUID,
    material_id: UUID,
) -> Decimal:
    signed_quantity = case(
        (MaterialStockTransaction.direction == StockDirection.INFLOW, MaterialStockTransaction.quantity),
        else_=-MaterialStockTransaction.quantity,
    )
    value = await db.scalar(
        select(func.coalesce(func.sum(signed_quantity), 0)).where(
            MaterialStockTransaction.organization_id == organization_id,
            MaterialStockTransaction.project_id == project_id,
            MaterialStockTransaction.stock_location_id == stock_location_id,
            MaterialStockTransaction.material_id == material_id,
        )
    )
    return Decimal(value or 0)


async def list_stock_balances(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    stock_location_id: UUID | None = None,
    material_id: UUID | None = None,
) -> list[dict[str, object]]:
    signed_quantity = case(
        (MaterialStockTransaction.direction == StockDirection.INFLOW, MaterialStockTransaction.quantity),
        else_=-MaterialStockTransaction.quantity,
    )
    statement = (
        select(
            MaterialStockTransaction.stock_location_id,
            MaterialStockTransaction.material_id,
            MaterialStockTransaction.unit_code,
            func.sum(signed_quantity).label("quantity_on_hand"),
        )
        .where(
            MaterialStockTransaction.organization_id == organization_id,
            MaterialStockTransaction.project_id == project_id,
        )
        .group_by(
            MaterialStockTransaction.stock_location_id,
            MaterialStockTransaction.material_id,
            MaterialStockTransaction.unit_code,
        )
        .order_by(
            MaterialStockTransaction.stock_location_id,
            MaterialStockTransaction.material_id,
        )
    )
    if stock_location_id is not None:
        statement = statement.where(
            MaterialStockTransaction.stock_location_id == stock_location_id
        )
    if material_id is not None:
        statement = statement.where(MaterialStockTransaction.material_id == material_id)
    rows = (await db.execute(statement)).all()
    return [
        {
            "stock_location_id": row.stock_location_id,
            "material_id": row.material_id,
            "unit_code": row.unit_code,
            "quantity_on_hand": Decimal(row.quantity_on_hand or 0),
        }
        for row in rows
    ]


async def record_goods_receipt_stock(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    receipt: GoodsReceipt,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> list[MaterialStockTransaction]:
    if receipt.stock_location_id is None:
        raise InventoryValidationError(
            "A stock location is required before a goods receipt can be received"
        )
    await require_stock_location(
        db,
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=receipt.stock_location_id,
        lock=True,
    )
    purchase_order = await db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == receipt.purchase_order_id,
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.project_id == project_id,
        )
    )
    if purchase_order is None:
        raise InventoryValidationError("Purchase order was not found for this goods receipt")

    receipt_lines = list(
        (
            await db.scalars(
                select(GoodsReceiptLine).where(
                    GoodsReceiptLine.organization_id == organization_id,
                    GoodsReceiptLine.project_id == project_id,
                    GoodsReceiptLine.goods_receipt_id == receipt.id,
                )
            )
        ).all()
    )
    po_line_ids = {line.purchase_order_line_id for line in receipt_lines}
    po_lines = {
        row.id: row
        for row in (
            await db.scalars(
                select(PurchaseOrderLine).where(
                    PurchaseOrderLine.organization_id == organization_id,
                    PurchaseOrderLine.project_id == project_id,
                    PurchaseOrderLine.id.in_(po_line_ids),
                )
            )
        ).all()
    }
    requisition_line_ids = {
        row.requisition_line_id
        for row in po_lines.values()
        if row.requisition_line_id is not None
    }
    requisition_lines: dict[UUID, PurchaseRequisitionLine] = {}
    if requisition_line_ids:
        requisition_lines = {
            row.id: row
            for row in (
                await db.scalars(
                    select(PurchaseRequisitionLine).where(
                        PurchaseRequisitionLine.organization_id == organization_id,
                        PurchaseRequisitionLine.project_id == project_id,
                        PurchaseRequisitionLine.id.in_(requisition_line_ids),
                    )
                )
            ).all()
        }
    material_ids = {
        row.material_id for row in po_lines.values() if row.material_id is not None
    }
    materials = {
        row.id: row
        for row in (
            await db.scalars(
                select(Material).where(
                    Material.organization_id == organization_id,
                    Material.id.in_(material_ids),
                )
            )
        ).all()
    } if material_ids else {}

    created: list[MaterialStockTransaction] = []
    for receipt_line in receipt_lines:
        if receipt_line.accepted_quantity <= 0:
            continue
        po_line = po_lines.get(receipt_line.purchase_order_line_id)
        if po_line is None:
            raise InventoryValidationError("Purchase order line was not found for goods receipt")
        if po_line.material_id is None:
            continue
        material = materials.get(po_line.material_id)
        if material is None:
            raise InventoryValidationError("Material master was not found for goods receipt line")
        unit_code = receipt_line.unit_code.strip()
        if unit_code.casefold() != po_line.unit_code.strip().casefold():
            raise InventoryValidationError(
                "Goods receipt unit must match its purchase order line until governed UOM conversion is configured"
            )
        if unit_code.casefold() != material.default_unit_code.strip().casefold():
            raise InventoryValidationError(
                "Goods receipt unit must match the Material default unit until governed UOM conversion is configured"
            )
        existing = await db.scalar(
            select(MaterialStockTransaction).where(
                MaterialStockTransaction.organization_id == organization_id,
                MaterialStockTransaction.project_id == project_id,
                MaterialStockTransaction.source_type == StockSourceType.GOODS_RECEIPT,
                MaterialStockTransaction.source_record_id == receipt_line.id,
                MaterialStockTransaction.direction == StockDirection.INFLOW,
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        requisition_line = (
            requisition_lines.get(po_line.requisition_line_id)
            if po_line.requisition_line_id is not None
            else None
        )
        transaction = MaterialStockTransaction(
            organization_id=organization_id,
            project_id=project_id,
            stock_location_id=receipt.stock_location_id,
            material_id=po_line.material_id,
            wbs_code_id=po_line.wbs_code_id,
            boq_item_id=requisition_line.boq_item_id if requisition_line is not None else None,
            transaction_type=StockTransactionType.GRN_RECEIPT,
            direction=StockDirection.INFLOW,
            quantity=receipt_line.accepted_quantity,
            unit_code=unit_code,
            occurred_at=receipt.received_at,
            source_type=StockSourceType.GOODS_RECEIPT,
            source_record_id=receipt_line.id,
            source_parent_id=receipt.id,
            source_reference=receipt.number,
            unit_cost_snapshot=po_line.unit_price,
            currency_code=purchase_order.currency_code.upper(),
            created_by_membership_id=receipt.received_by_membership_id,
            notes=receipt_line.remarks,
        )
        db.add(transaction)
        created.append(transaction)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.inventory.grn.posted",
        target_type="goods_receipt",
        target_id=str(receipt.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "stock_location_id": str(receipt.stock_location_id),
            "stock_transaction_count": len(created),
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="materials.inventory.changed",
        entity_type="goods_receipt",
        entity_id=receipt.id,
        entity_version=receipt.revision,
        required_permission_key="materials.inventory.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "source_type": StockSourceType.GOODS_RECEIPT.value,
            "stock_location_id": str(receipt.stock_location_id),
            "transaction_count": len(created),
        },
    )
    return created


async def record_material_consumption_stock(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    stock_location_id: UUID,
    material_id: UUID,
    wbs_code_id: UUID | None,
    boq_item_id: UUID | None,
    quantity: Decimal,
    unit_code: str,
    consumption_date: date,
    consumption_id: UUID,
    source_reference: str | None,
    unit_cost_snapshot: Decimal | None,
    currency_code: str,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MaterialStockTransaction:
    await require_stock_location(
        db,
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=stock_location_id,
        lock=True,
    )
    existing = await db.scalar(
        select(MaterialStockTransaction).where(
            MaterialStockTransaction.organization_id == organization_id,
            MaterialStockTransaction.project_id == project_id,
            MaterialStockTransaction.source_type == StockSourceType.MATERIAL_CONSUMPTION,
            MaterialStockTransaction.source_record_id == consumption_id,
            MaterialStockTransaction.direction == StockDirection.OUTFLOW,
        )
    )
    if existing is not None:
        return existing

    material = await db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.organization_id == organization_id,
        )
    )
    if material is None:
        raise InventoryValidationError("Material master was not found")
    if unit_code.strip().casefold() != material.default_unit_code.strip().casefold():
        raise InventoryValidationError(
            "Material consumption unit must match the Material default unit until governed UOM conversion is configured"
        )
    available = await stock_quantity_on_hand(
        db,
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=stock_location_id,
        material_id=material_id,
    )
    if quantity > available:
        raise InventoryValidationError(
            f"Insufficient stock: {available} {unit_code} available at this location"
        )

    transaction = MaterialStockTransaction(
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=stock_location_id,
        material_id=material_id,
        wbs_code_id=wbs_code_id,
        boq_item_id=boq_item_id,
        transaction_type=StockTransactionType.CONSUMPTION,
        direction=StockDirection.OUTFLOW,
        quantity=quantity,
        unit_code=unit_code.strip(),
        occurred_at=datetime.combine(consumption_date, time.min, tzinfo=UTC),
        source_type=StockSourceType.MATERIAL_CONSUMPTION,
        source_record_id=consumption_id,
        source_reference=source_reference or f"Material consumption {consumption_id}",
        unit_cost_snapshot=unit_cost_snapshot,
        currency_code=currency_code.upper(),
        created_by_membership_id=membership_id,
    )
    db.add(transaction)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.inventory.consumption.posted",
        target_type="material_stock_transaction",
        target_id=str(transaction.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "stock_location_id": str(stock_location_id),
            "material_id": str(material_id),
            "quantity": quantity,
            "unit_code": unit_code,
            "source_record_id": str(consumption_id),
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="materials.inventory.changed",
        entity_type="material_stock_transaction",
        entity_id=transaction.id,
        required_permission_key="materials.inventory.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "source_type": StockSourceType.MATERIAL_CONSUMPTION.value,
            "stock_location_id": str(stock_location_id),
            "material_id": str(material_id),
            "quantity": str(quantity),
            "direction": StockDirection.OUTFLOW.value,
        },
    )
    return transaction
