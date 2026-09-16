from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.procurement.models import PurchaseOrder
from app.modules.procurement.po_revision_models import PurchaseOrderRevision
from app.modules.procurement.po_revision_schemas import (
    PurchaseOrderAmendmentCreate,
    PurchaseOrderRevisionRead,
)
from app.modules.procurement.po_revision_service import (
    list_purchase_order_revisions,
    start_purchase_order_amendment,
)
from app.modules.procurement.schemas import PurchaseOrderRead
from app.modules.procurement.service import ProcurementConflictError, ProcurementValidationError
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["procurement"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, ProcurementConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/revisions",
    response_model=list[PurchaseOrderRevisionRead],
)
async def list_purchase_order_revision_history(
    project_id: UUID,
    purchase_order_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[PurchaseOrderRevision]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    try:
        return await list_purchase_order_revisions(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            purchase_order_id=purchase_order_id,
        )
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/amendments",
    response_model=PurchaseOrderRead,
)
async def create_purchase_order_amendment(
    project_id: UUID,
    purchase_order_id: UUID,
    payload: PurchaseOrderAmendmentCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PurchaseOrder:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await start_purchase_order_amendment(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            purchase_order_id=purchase_order_id,
            expected_revision=payload.expected_revision,
            reason=payload.reason,
            values=payload.model_dump(exclude={"expected_revision", "reason"}),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
