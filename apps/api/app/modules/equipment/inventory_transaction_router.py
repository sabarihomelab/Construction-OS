from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.equipment.inventory_control_schemas import (
    ManualStockTransactionCreate,
    StockTransferCreate,
    StockTransferRead,
)
from app.modules.equipment.inventory_models import MaterialStockTransaction
from app.modules.equipment.inventory_schemas import MaterialStockTransactionRead
from app.modules.equipment.inventory_service import InventoryConflictError, InventoryValidationError
from app.modules.equipment.inventory_transaction_service import (
    record_manual_stock_transaction,
    transfer_stock,
)
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["materials"])


def _project_permission(context, project_id: UUID, key: str) -> None:
    if not project_permission_is_allowed(
        key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={item: set(values) for item, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, InventoryConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/materials/stock-transactions/manual",
    response_model=MaterialStockTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_manual_stock_transaction(
    project_id: UUID,
    payload: ManualStockTransactionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MaterialStockTransaction:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.inventory.manage")
    try:
        row = await record_manual_stock_transaction(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (InventoryConflictError, InventoryValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/materials/stock-transfers",
    response_model=StockTransferRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_stock_transfer(
    project_id: UUID,
    payload: StockTransferCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> StockTransferRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.inventory.manage")
    try:
        outflow, inflow = await transfer_stock(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(outflow)
        await db.refresh(inflow)
        return StockTransferRead(
            transfer_id=payload.client_transfer_id,
            outflow=MaterialStockTransactionRead.model_validate(outflow),
            inflow=MaterialStockTransactionRead.model_validate(inflow),
        )
    except (InventoryConflictError, InventoryValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
