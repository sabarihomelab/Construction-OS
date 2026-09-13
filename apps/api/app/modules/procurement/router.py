from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.procurement.inventory_bridge import (
    create_goods_receipt_with_stock_location,
    receive_goods_receipt_with_inventory,
)
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RequisitionStatus,
)
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptLineCreate,
    GoodsReceiptLineRead,
    GoodsReceiptRead,
    GoodsReceiptReceiveAction,
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineRead,
    PurchaseOrderRead,
    RequisitionCreate,
    RequisitionLineCreate,
    RequisitionLineRead,
    RequisitionRead,
    RevisionAction,
)
from app.modules.procurement.service import (
    ProcurementConflictError,
    ProcurementValidationError,
    add_goods_receipt_line,
    add_purchase_order_line,
    add_requisition_line,
    create_purchase_order,
    create_requisition,
    transition_purchase_order,
    transition_requisition,
)
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


@router.get("/projects/{project_id}/procurement/requisitions", response_model=list[RequisitionRead])
async def list_requisitions(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[PurchaseRequisition]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.requisition.view")
    rows = await db.scalars(
        select(PurchaseRequisition)
        .where(
            PurchaseRequisition.organization_id == context.organization_id,
            PurchaseRequisition.project_id == project_id,
        )
        .order_by(PurchaseRequisition.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/requisitions",
    response_model=RequisitionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_requisition_route(
    project_id: UUID,
    payload: RequisitionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PurchaseRequisition:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.requisition.create")
    try:
        row = await create_requisition(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            requested_by_membership_id=session.membership_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/procurement/requisitions/{requisition_id}/lines",
    response_model=list[RequisitionLineRead],
)
async def list_requisition_lines(
    project_id: UUID,
    requisition_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[PurchaseRequisitionLine]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.requisition.view")
    rows = await db.scalars(
        select(PurchaseRequisitionLine)
        .where(
            PurchaseRequisitionLine.organization_id == context.organization_id,
            PurchaseRequisitionLine.project_id == project_id,
            PurchaseRequisitionLine.requisition_id == requisition_id,
        )
        .order_by(PurchaseRequisitionLine.line_number)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/requisitions/{requisition_id}/lines",
    response_model=RequisitionLineRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_requisition_line_route(
    project_id: UUID,
    requisition_id: UUID,
    payload: RequisitionLineCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PurchaseRequisitionLine:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.requisition.manage")
    try:
        row = await add_requisition_line(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            requisition_id=requisition_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


async def _requisition_transition(
    project_id: UUID,
    requisition_id: UUID,
    payload: RevisionAction,
    target: RequisitionStatus,
    permission: str,
    db: DbSession,
    session: CurrentSession,
) -> PurchaseRequisition:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, permission)
    try:
        row = await transition_requisition(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            requisition_id=requisition_id,
            expected_revision=payload.expected_revision,
            target=target,
            actor_user_id=session.user_id,
            actor_membership_id=session.membership_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/procurement/requisitions/{requisition_id}/submit", response_model=RequisitionRead)
async def submit_requisition(project_id: UUID, requisition_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseRequisition:
    return await _requisition_transition(project_id, requisition_id, payload, RequisitionStatus.SUBMITTED, "procurement.requisition.submit", db, session)


@router.post("/projects/{project_id}/procurement/requisitions/{requisition_id}/approve", response_model=RequisitionRead)
async def approve_requisition(project_id: UUID, requisition_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseRequisition:
    return await _requisition_transition(project_id, requisition_id, payload, RequisitionStatus.APPROVED, "procurement.requisition.approve", db, session)


@router.post("/projects/{project_id}/procurement/requisitions/{requisition_id}/reject", response_model=RequisitionRead)
async def reject_requisition(project_id: UUID, requisition_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseRequisition:
    return await _requisition_transition(project_id, requisition_id, payload, RequisitionStatus.REJECTED, "procurement.requisition.approve", db, session)


@router.get("/projects/{project_id}/procurement/purchase-orders", response_model=list[PurchaseOrderRead])
async def list_purchase_orders(project_id: UUID, db: DbSession, session: CurrentSession) -> list[PurchaseOrder]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.organization_id == context.organization_id, PurchaseOrder.project_id == project_id)
        .order_by(PurchaseOrder.created_at.desc())
    )
    return list(rows.all())


@router.post("/projects/{project_id}/procurement/purchase-orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_purchase_order_route(project_id: UUID, payload: PurchaseOrderCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseOrder:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.create")
    try:
        row = await create_purchase_order(db, organization_id=context.organization_id, project_id=project_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/lines", response_model=list[PurchaseOrderLineRead])
async def list_purchase_order_lines(project_id: UUID, purchase_order_id: UUID, db: DbSession, session: CurrentSession) -> list[PurchaseOrderLine]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.organization_id == context.organization_id, PurchaseOrderLine.project_id == project_id, PurchaseOrderLine.purchase_order_id == purchase_order_id).order_by(PurchaseOrderLine.line_number))
    return list(rows.all())


@router.post("/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/lines", response_model=PurchaseOrderLineRead, status_code=status.HTTP_201_CREATED)
async def add_purchase_order_line_route(project_id: UUID, purchase_order_id: UUID, payload: PurchaseOrderLineCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseOrderLine:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await add_purchase_order_line(db, organization_id=context.organization_id, project_id=project_id, purchase_order_id=purchase_order_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


async def _po_transition(project_id: UUID, purchase_order_id: UUID, payload: RevisionAction, target: PurchaseOrderStatus, permission: str, db: DbSession, session: CurrentSession) -> PurchaseOrder:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, permission)
    try:
        row = await transition_purchase_order(db, organization_id=context.organization_id, project_id=project_id, purchase_order_id=purchase_order_id, expected_revision=payload.expected_revision, target=target, actor_user_id=session.user_id, actor_membership_id=session.membership_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/submit", response_model=PurchaseOrderRead)
async def submit_purchase_order(project_id: UUID, purchase_order_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseOrder:
    return await _po_transition(project_id, purchase_order_id, payload, PurchaseOrderStatus.SUBMITTED, "procurement.purchase_order.submit", db, session)


@router.post("/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/approve", response_model=PurchaseOrderRead)
async def approve_purchase_order(project_id: UUID, purchase_order_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseOrder:
    return await _po_transition(project_id, purchase_order_id, payload, PurchaseOrderStatus.APPROVED, "procurement.purchase_order.approve", db, session)


@router.post("/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/issue", response_model=PurchaseOrderRead)
async def issue_purchase_order(project_id: UUID, purchase_order_id: UUID, payload: RevisionAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> PurchaseOrder:
    return await _po_transition(project_id, purchase_order_id, payload, PurchaseOrderStatus.ISSUED, "procurement.purchase_order.issue", db, session)


@router.get("/projects/{project_id}/procurement/goods-receipts", response_model=list[GoodsReceiptRead])
async def list_goods_receipts(project_id: UUID, db: DbSession, session: CurrentSession) -> list[GoodsReceipt]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.receipt.view")
    rows = await db.scalars(select(GoodsReceipt).where(GoodsReceipt.organization_id == context.organization_id, GoodsReceipt.project_id == project_id).order_by(GoodsReceipt.received_at.desc()))
    return list(rows.all())


@router.post("/projects/{project_id}/procurement/goods-receipts", response_model=GoodsReceiptRead, status_code=status.HTTP_201_CREATED)
async def create_goods_receipt_route(project_id: UUID, payload: GoodsReceiptCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> GoodsReceipt:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.receipt.create")
    try:
        row = await create_goods_receipt_with_stock_location(db, organization_id=context.organization_id, project_id=project_id, received_by_membership_id=session.membership_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/procurement/goods-receipts/{goods_receipt_id}/lines", response_model=list[GoodsReceiptLineRead])
async def list_goods_receipt_lines(project_id: UUID, goods_receipt_id: UUID, db: DbSession, session: CurrentSession) -> list[GoodsReceiptLine]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.receipt.view")
    rows = await db.scalars(select(GoodsReceiptLine).where(GoodsReceiptLine.organization_id == context.organization_id, GoodsReceiptLine.project_id == project_id, GoodsReceiptLine.goods_receipt_id == goods_receipt_id).order_by(GoodsReceiptLine.created_at))
    return list(rows.all())


@router.post("/projects/{project_id}/procurement/goods-receipts/{goods_receipt_id}/lines", response_model=GoodsReceiptLineRead, status_code=status.HTTP_201_CREATED)
async def add_goods_receipt_line_route(project_id: UUID, goods_receipt_id: UUID, payload: GoodsReceiptLineCreate, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> GoodsReceiptLine:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.receipt.manage")
    try:
        row = await add_goods_receipt_line(db, organization_id=context.organization_id, project_id=project_id, goods_receipt_id=goods_receipt_id, values=payload.model_dump(), actor_user_id=session.user_id, session_id=session.id)
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/procurement/goods-receipts/{goods_receipt_id}/receive", response_model=GoodsReceiptRead)
async def receive_goods_receipt_route(project_id: UUID, goods_receipt_id: UUID, payload: GoodsReceiptReceiveAction, db: DbSession, session: CurrentSession, _csrf: CsrfProtected) -> GoodsReceipt:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.receipt.receive")
    try:
        row = await receive_goods_receipt_with_inventory(db, organization_id=context.organization_id, project_id=project_id, goods_receipt_id=goods_receipt_id, expected_revision=payload.expected_revision, actor_user_id=session.user_id, stock_location_id=payload.stock_location_id, session_id=session.id, reason=payload.reason)
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)