from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.equipment.inventory_models import (
    MaterialStockLocation,
    MaterialStockTransaction,
)
from app.modules.equipment.inventory_schemas import (
    MaterialStockBalanceRead,
    MaterialStockLocationCreate,
    MaterialStockLocationRead,
    MaterialStockTransactionRead,
)
from app.modules.equipment.inventory_service import (
    InventoryConflictError,
    InventoryValidationError,
    create_stock_location,
    list_stock_balances,
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


@router.get(
    "/projects/{project_id}/materials/stock-locations",
    response_model=list[MaterialStockLocationRead],
)
async def list_material_stock_locations(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MaterialStockLocation]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.inventory.view")
    rows = await db.scalars(
        select(MaterialStockLocation)
        .where(
            MaterialStockLocation.organization_id == context.organization_id,
            MaterialStockLocation.project_id == project_id,
        )
        .order_by(MaterialStockLocation.code)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/materials/stock-locations",
    response_model=MaterialStockLocationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_stock_location_route(
    project_id: UUID,
    payload: MaterialStockLocationCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MaterialStockLocation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.inventory.manage")
    try:
        row = await create_stock_location(
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


@router.get(
    "/projects/{project_id}/materials/stock-transactions",
    response_model=list[MaterialStockTransactionRead],
)
async def list_material_stock_transactions(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    stock_location_id: UUID | None = None,
    material_id: UUID | None = None,
) -> list[MaterialStockTransaction]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.inventory.view")
    statement = select(MaterialStockTransaction).where(
        MaterialStockTransaction.organization_id == context.organization_id,
        MaterialStockTransaction.project_id == project_id,
    )
    if stock_location_id is not None:
        statement = statement.where(
            MaterialStockTransaction.stock_location_id == stock_location_id
        )
    if material_id is not None:
        statement = statement.where(MaterialStockTransaction.material_id == material_id)
    rows = await db.scalars(
        statement.order_by(
            MaterialStockTransaction.occurred_at.desc(),
            MaterialStockTransaction.created_at.desc(),
        )
    )
    return list(rows.all())


@router.get(
    "/projects/{project_id}/materials/stock-balances",
    response_model=list[MaterialStockBalanceRead],
)
async def list_material_stock_balances(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    stock_location_id: UUID | None = None,
    material_id: UUID | None = None,
) -> list[MaterialStockBalanceRead]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.inventory.view")
    rows = await list_stock_balances(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        stock_location_id=stock_location_id,
        material_id=material_id,
    )
    return [MaterialStockBalanceRead.model_validate(row) for row in rows]
