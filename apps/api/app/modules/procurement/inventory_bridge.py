from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipment.inventory_service import (
    InventoryValidationError,
    record_goods_receipt_stock,
    require_stock_location,
)
from app.modules.procurement.models import GoodsReceipt
from app.modules.procurement.service import (
    ProcurementValidationError,
    create_goods_receipt,
    receive_goods_receipt,
)


async def create_goods_receipt_with_stock_location(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    received_by_membership_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> GoodsReceipt:
    stock_location_id = values.get("stock_location_id")
    if stock_location_id is not None:
        if not isinstance(stock_location_id, UUID):
            raise ProcurementValidationError("stock_location_id must be a UUID")
        try:
            await require_stock_location(
                db,
                organization_id=organization_id,
                project_id=project_id,
                stock_location_id=stock_location_id,
            )
        except InventoryValidationError as exc:
            raise ProcurementValidationError(str(exc)) from exc

    row = await create_goods_receipt(
        db,
        organization_id=organization_id,
        project_id=project_id,
        received_by_membership_id=received_by_membership_id,
        values=values,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    row.stock_location_id = stock_location_id if isinstance(stock_location_id, UUID) else None
    await db.flush()
    return row


async def receive_goods_receipt_with_inventory(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    goods_receipt_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    stock_location_id: UUID | None = None,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> GoodsReceipt:
    row = await receive_goods_receipt(
        db,
        organization_id=organization_id,
        project_id=project_id,
        goods_receipt_id=goods_receipt_id,
        expected_revision=expected_revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
        reason=reason,
    )
    if stock_location_id is not None:
        try:
            await require_stock_location(
                db,
                organization_id=organization_id,
                project_id=project_id,
                stock_location_id=stock_location_id,
            )
        except InventoryValidationError as exc:
            raise ProcurementValidationError(str(exc)) from exc
        row.stock_location_id = stock_location_id
        await db.flush()

    try:
        await record_goods_receipt_stock(
            db,
            organization_id=organization_id,
            project_id=project_id,
            receipt=row,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    except InventoryValidationError as exc:
        raise ProcurementValidationError(str(exc)) from exc
    return row
