from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.equipment.consumption_models import MaterialConsumption
from app.modules.equipment.consumption_schemas import (
    MaterialConsumptionCreate,
    MaterialConsumptionPost,
    MaterialConsumptionRead,
)
from app.modules.equipment.consumption_service import (
    MaterialConsumptionConflictError,
    MaterialConsumptionValidationError,
    create_material_consumption,
    post_material_consumption,
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
    if isinstance(exc, MaterialConsumptionConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/materials/consumptions",
    response_model=list[MaterialConsumptionRead],
)
async def list_material_consumptions(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MaterialConsumption]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.delivery.view")
    rows = await db.scalars(
        select(MaterialConsumption)
        .where(
            MaterialConsumption.organization_id == context.organization_id,
            MaterialConsumption.project_id == project_id,
        )
        .order_by(
            MaterialConsumption.consumption_date.desc(),
            MaterialConsumption.created_at.desc(),
        )
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/materials/consumptions",
    response_model=MaterialConsumptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_consumption_route(
    project_id: UUID,
    payload: MaterialConsumptionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MaterialConsumption:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.delivery.manage")
    try:
        row = await create_material_consumption(
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
    except (MaterialConsumptionConflictError, MaterialConsumptionValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/materials/consumptions/{consumption_id}/post",
    response_model=MaterialConsumptionRead,
)
async def post_material_consumption_route(
    project_id: UUID,
    consumption_id: UUID,
    payload: MaterialConsumptionPost,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MaterialConsumption:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "materials.delivery.manage")
    try:
        row = await post_material_consumption(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            consumption_id=consumption_id,
            membership_id=context.membership_id,
            expected_revision=payload.expected_revision,
            unit_cost=payload.unit_cost,
            cost_basis=payload.cost_basis,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MaterialConsumptionConflictError, MaterialConsumptionValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
