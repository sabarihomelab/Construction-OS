from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.equipment.inventory_models import (
    MaterialStockTransaction,
    StockDirection,
    StockSourceType,
    StockTransactionType,
)
from app.modules.equipment.inventory_service import (
    InventoryConflictError,
    InventoryValidationError,
    _require_project_membership,
    require_stock_location,
    stock_quantity_on_hand,
)
from app.modules.equipment.models import Material
from app.modules.events.service import enqueue_event


_MANUAL_DIRECTIONS: dict[StockTransactionType, StockDirection] = {
    StockTransactionType.OPENING_BALANCE: StockDirection.INFLOW,
    StockTransactionType.ISSUE: StockDirection.OUTFLOW,
    StockTransactionType.RETURN_IN: StockDirection.INFLOW,
    StockTransactionType.RETURN_OUT: StockDirection.OUTFLOW,
    StockTransactionType.REJECTION: StockDirection.OUTFLOW,
    StockTransactionType.WASTAGE: StockDirection.OUTFLOW,
    StockTransactionType.DAMAGE: StockDirection.OUTFLOW,
    StockTransactionType.ADJUSTMENT_IN: StockDirection.INFLOW,
    StockTransactionType.ADJUSTMENT_OUT: StockDirection.OUTFLOW,
}


async def _require_material(
    db: AsyncSession,
    *,
    organization_id: UUID,
    material_id: UUID,
) -> Material:
    material = await db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.organization_id == organization_id,
        )
    )
    if material is None:
        raise InventoryValidationError("Material master was not found")
    return material


def _commercial_snapshot(values: Mapping[str, object]) -> tuple[Decimal | None, str | None]:
    unit_cost = values.get("unit_cost_snapshot")
    currency = values.get("currency_code")
    if (unit_cost is None) != (currency is None):
        raise InventoryValidationError(
            "Unit cost snapshot and currency must be supplied together"
        )
    return (
        Decimal(unit_cost) if unit_cost is not None else None,
        str(currency).upper() if currency is not None else None,
    )


async def _validate_related_transaction(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    material_id: UUID,
    related_transaction_id: UUID | None,
) -> None:
    if related_transaction_id is None:
        return
    found = await db.scalar(
        select(MaterialStockTransaction.id).where(
            MaterialStockTransaction.id == related_transaction_id,
            MaterialStockTransaction.organization_id == organization_id,
            MaterialStockTransaction.project_id == project_id,
            MaterialStockTransaction.material_id == material_id,
        )
    )
    if found is None:
        raise InventoryValidationError(
            "Related stock transaction was not found for this project and material"
        )


async def record_manual_stock_transaction(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> MaterialStockTransaction:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    transaction_type = values.get("transaction_type")
    if not isinstance(transaction_type, StockTransactionType):
        raise InventoryValidationError("A valid stock transaction type is required")
    direction = _MANUAL_DIRECTIONS.get(transaction_type)
    if direction is None:
        raise InventoryValidationError(
            "This transaction type is system-generated or must use the transfer endpoint"
        )

    client_transaction_id = values.get("client_transaction_id")
    stock_location_id = values.get("stock_location_id")
    material_id = values.get("material_id")
    occurred_at = values.get("occurred_at")
    quantity = Decimal(values.get("quantity") or 0)
    if not isinstance(client_transaction_id, UUID):
        raise InventoryValidationError("Client transaction id is required")
    if not isinstance(stock_location_id, UUID) or not isinstance(material_id, UUID):
        raise InventoryValidationError("Stock location and material are required")
    if not isinstance(occurred_at, datetime):
        raise InventoryValidationError("Transaction timestamp is required")
    if quantity <= 0:
        raise InventoryValidationError("Stock transaction quantity must be greater than zero")

    existing = await db.scalar(
        select(MaterialStockTransaction).where(
            MaterialStockTransaction.organization_id == organization_id,
            MaterialStockTransaction.project_id == project_id,
            MaterialStockTransaction.source_type == StockSourceType.MANUAL_ADJUSTMENT,
            MaterialStockTransaction.source_record_id == client_transaction_id,
            MaterialStockTransaction.direction == direction,
        )
    )
    if existing is not None:
        if (
            existing.transaction_type != transaction_type
            or existing.stock_location_id != stock_location_id
            or existing.material_id != material_id
            or existing.quantity != quantity
        ):
            raise InventoryConflictError(
                "Client transaction id was already used for a different stock posting"
            )
        return existing

    await require_stock_location(
        db,
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=stock_location_id,
        lock=True,
    )
    material = await _require_material(
        db,
        organization_id=organization_id,
        material_id=material_id,
    )
    related_transaction_id = values.get("related_transaction_id")
    await _validate_related_transaction(
        db,
        organization_id=organization_id,
        project_id=project_id,
        material_id=material_id,
        related_transaction_id=(
            related_transaction_id if isinstance(related_transaction_id, UUID) else None
        ),
    )
    if transaction_type == StockTransactionType.OPENING_BALANCE:
        prior_count = await db.scalar(
            select(func.count(MaterialStockTransaction.id)).where(
                MaterialStockTransaction.organization_id == organization_id,
                MaterialStockTransaction.project_id == project_id,
                MaterialStockTransaction.stock_location_id == stock_location_id,
                MaterialStockTransaction.material_id == material_id,
            )
        )
        if prior_count:
            raise InventoryValidationError(
                "Opening balance can only be posted before other transactions for this material and location"
            )
    if direction == StockDirection.OUTFLOW:
        available = await stock_quantity_on_hand(
            db,
            organization_id=organization_id,
            project_id=project_id,
            stock_location_id=stock_location_id,
            material_id=material_id,
        )
        if quantity > available:
            raise InventoryValidationError(
                f"Insufficient stock: {available} {material.default_unit_code} available at this location"
            )

    unit_cost, currency_code = _commercial_snapshot(values)
    reason = str(values.get("reason") or "").strip()
    if not reason:
        raise InventoryValidationError("Reason is required for a manual stock posting")
    source_reference = str(values.get("source_reference") or "").strip() or None
    transaction = MaterialStockTransaction(
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=stock_location_id,
        material_id=material_id,
        wbs_code_id=values.get("wbs_code_id"),
        boq_item_id=values.get("boq_item_id"),
        transaction_type=transaction_type,
        direction=direction,
        quantity=quantity,
        unit_code=material.default_unit_code,
        occurred_at=occurred_at,
        source_type=StockSourceType.MANUAL_ADJUSTMENT,
        source_record_id=client_transaction_id,
        source_parent_id=(
            related_transaction_id if isinstance(related_transaction_id, UUID) else None
        ),
        source_reference=source_reference,
        unit_cost_snapshot=unit_cost,
        currency_code=currency_code,
        created_by_membership_id=membership_id,
        notes=reason,
    )
    db.add(transaction)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"materials.inventory.{transaction_type.value}.posted",
        target_type="material_stock_transaction",
        target_id=str(transaction.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "project_id": str(project_id),
            "stock_location_id": str(stock_location_id),
            "material_id": str(material_id),
            "quantity": str(quantity),
            "unit_code": material.default_unit_code,
            "direction": direction.value,
            "source_record_id": str(client_transaction_id),
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
            "transaction_type": transaction_type.value,
            "stock_location_id": str(stock_location_id),
            "material_id": str(material_id),
            "quantity": str(quantity),
            "direction": direction.value,
        },
    )
    return transaction


async def transfer_stock(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> tuple[MaterialStockTransaction, MaterialStockTransaction]:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    transfer_id = values.get("client_transfer_id")
    from_location_id = values.get("from_stock_location_id")
    to_location_id = values.get("to_stock_location_id")
    material_id = values.get("material_id")
    occurred_at = values.get("occurred_at")
    quantity = Decimal(values.get("quantity") or 0)
    if not all(isinstance(value, UUID) for value in (transfer_id, from_location_id, to_location_id, material_id)):
        raise InventoryValidationError(
            "Transfer id, source location, destination location and material are required"
        )
    if from_location_id == to_location_id:
        raise InventoryValidationError("Source and destination stock locations must differ")
    if not isinstance(occurred_at, datetime):
        raise InventoryValidationError("Transfer timestamp is required")
    if quantity <= 0:
        raise InventoryValidationError("Transfer quantity must be greater than zero")

    existing_rows = list(
        (
            await db.scalars(
                select(MaterialStockTransaction).where(
                    MaterialStockTransaction.organization_id == organization_id,
                    MaterialStockTransaction.project_id == project_id,
                    MaterialStockTransaction.source_type == StockSourceType.MANUAL_ADJUSTMENT,
                    MaterialStockTransaction.source_record_id == transfer_id,
                )
            )
        ).all()
    )
    if existing_rows:
        by_type = {row.transaction_type: row for row in existing_rows}
        outflow = by_type.get(StockTransactionType.TRANSFER_OUT)
        inflow = by_type.get(StockTransactionType.TRANSFER_IN)
        if outflow is None or inflow is None:
            raise InventoryConflictError("Transfer id is already used by an incomplete stock posting")
        if (
            outflow.stock_location_id != from_location_id
            or inflow.stock_location_id != to_location_id
            or outflow.material_id != material_id
            or inflow.material_id != material_id
            or outflow.quantity != quantity
            or inflow.quantity != quantity
        ):
            raise InventoryConflictError("Transfer id was already used for a different transfer")
        return outflow, inflow

    for location_id in sorted((from_location_id, to_location_id), key=str):
        await require_stock_location(
            db,
            organization_id=organization_id,
            project_id=project_id,
            stock_location_id=location_id,
            lock=True,
        )
    material = await _require_material(
        db,
        organization_id=organization_id,
        material_id=material_id,
    )
    available = await stock_quantity_on_hand(
        db,
        organization_id=organization_id,
        project_id=project_id,
        stock_location_id=from_location_id,
        material_id=material_id,
    )
    if quantity > available:
        raise InventoryValidationError(
            f"Insufficient stock: {available} {material.default_unit_code} available at source location"
        )
    unit_cost, currency_code = _commercial_snapshot(values)
    reason = str(values.get("reason") or "").strip()
    if not reason:
        raise InventoryValidationError("Reason is required for a stock transfer")
    source_reference = str(values.get("source_reference") or "").strip() or None
    common = {
        "organization_id": organization_id,
        "project_id": project_id,
        "material_id": material_id,
        "quantity": quantity,
        "unit_code": material.default_unit_code,
        "occurred_at": occurred_at,
        "source_type": StockSourceType.MANUAL_ADJUSTMENT,
        "source_record_id": transfer_id,
        "source_reference": source_reference,
        "unit_cost_snapshot": unit_cost,
        "currency_code": currency_code,
        "created_by_membership_id": membership_id,
        "notes": reason,
    }
    outflow = MaterialStockTransaction(
        **common,
        stock_location_id=from_location_id,
        transaction_type=StockTransactionType.TRANSFER_OUT,
        direction=StockDirection.OUTFLOW,
    )
    inflow = MaterialStockTransaction(
        **common,
        stock_location_id=to_location_id,
        transaction_type=StockTransactionType.TRANSFER_IN,
        direction=StockDirection.INFLOW,
    )
    db.add_all([outflow, inflow])
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.inventory.transfer.posted",
        target_type="material_stock_transfer",
        target_id=str(transfer_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "project_id": str(project_id),
            "from_stock_location_id": str(from_location_id),
            "to_stock_location_id": str(to_location_id),
            "material_id": str(material_id),
            "quantity": str(quantity),
            "unit_code": material.default_unit_code,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="materials.inventory.changed",
        entity_type="material_stock_transfer",
        entity_id=transfer_id,
        required_permission_key="materials.inventory.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "from_stock_location_id": str(from_location_id),
            "to_stock_location_id": str(to_location_id),
            "material_id": str(material_id),
            "quantity": str(quantity),
        },
    )
    return outflow, inflow
