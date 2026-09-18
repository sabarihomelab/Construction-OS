from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.procurement.models import PurchaseOrder
from app.modules.procurement.schemas import PurchaseOrderRead
from app.modules.procurement.service import ProcurementConflictError, ProcurementValidationError
from app.modules.procurement.sourcing_models import (
    PurchaseOrderSource,
    RequestForQuotation,
    RequestForQuotationLine,
    RFQStatus,
    RFQVendorInvitation,
    RFQVendorSelection,
    VendorQuotation,
    VendorQuotationLine,
    VendorQuotationStatus,
)
from app.modules.procurement.sourcing_schemas import (
    PurchaseOrderFromSelectionCreate,
    PurchaseOrderSourceRead,
    QuotationCreate,
    QuotationLineCreate,
    QuotationLineRead,
    QuotationRead,
    RFQComparisonRead,
    RFQCreate,
    RFQLineRead,
    RFQRead,
    RFQVendorInvite,
    RFQVendorRead,
    SourcingRevisionAction,
    VendorSelectionCreate,
    VendorSelectionRead,
)
from app.modules.procurement.sourcing_service import (
    add_quotation_line,
    build_rfq_comparison,
    create_purchase_order_from_selection,
    create_quotation,
    create_rfq,
    invite_rfq_vendor,
    select_rfq_vendor,
    transition_quotation,
    transition_rfq,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["procurement-sourcing"])


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


@router.get("/projects/{project_id}/procurement/rfqs", response_model=list[RFQRead])
async def list_rfqs(project_id: UUID, db: DbSession, session: CurrentSession) -> list[RequestForQuotation]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(RequestForQuotation)
        .where(
            RequestForQuotation.organization_id == context.organization_id,
            RequestForQuotation.project_id == project_id,
        )
        .order_by(RequestForQuotation.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/rfqs",
    response_model=RFQRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rfq_route(
    project_id: UUID,
    payload: RFQCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RequestForQuotation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await create_rfq(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
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


@router.get("/projects/{project_id}/procurement/rfqs/{rfq_id}", response_model=RFQRead)
async def get_rfq(
    project_id: UUID,
    rfq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> RequestForQuotation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    row = await db.scalar(
        select(RequestForQuotation).where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.organization_id == context.organization_id,
            RequestForQuotation.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
    return row


@router.get("/projects/{project_id}/procurement/rfqs/{rfq_id}/lines", response_model=list[RFQLineRead])
async def list_rfq_lines(
    project_id: UUID,
    rfq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RequestForQuotationLine]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(RequestForQuotationLine)
        .where(
            RequestForQuotationLine.organization_id == context.organization_id,
            RequestForQuotationLine.project_id == project_id,
            RequestForQuotationLine.rfq_id == rfq_id,
        )
        .order_by(RequestForQuotationLine.line_number)
    )
    return list(rows.all())


@router.get("/projects/{project_id}/procurement/rfqs/{rfq_id}/vendors", response_model=list[RFQVendorRead])
async def list_rfq_vendors(
    project_id: UUID,
    rfq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RFQVendorInvitation]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(RFQVendorInvitation)
        .where(
            RFQVendorInvitation.organization_id == context.organization_id,
            RFQVendorInvitation.project_id == project_id,
            RFQVendorInvitation.rfq_id == rfq_id,
        )
        .order_by(RFQVendorInvitation.invited_at)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/rfqs/{rfq_id}/vendors",
    response_model=RFQVendorRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_rfq_vendor_route(
    project_id: UUID,
    rfq_id: UUID,
    payload: RFQVendorInvite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RFQVendorInvitation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await invite_rfq_vendor(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            rfq_id=rfq_id,
            supplier_party_id=payload.supplier_party_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            notes=payload.notes,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


async def _rfq_transition_route(
    project_id: UUID,
    rfq_id: UUID,
    payload: SourcingRevisionAction,
    target: RFQStatus,
    db: DbSession,
    session: CurrentSession,
) -> RequestForQuotation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await transition_rfq(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            rfq_id=rfq_id,
            expected_revision=payload.expected_revision,
            target=target,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/procurement/rfqs/{rfq_id}/issue", response_model=RFQRead)
async def issue_rfq(
    project_id: UUID,
    rfq_id: UUID,
    payload: SourcingRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RequestForQuotation:
    return await _rfq_transition_route(project_id, rfq_id, payload, RFQStatus.ISSUED, db, session)


@router.post("/projects/{project_id}/procurement/rfqs/{rfq_id}/cancel", response_model=RFQRead)
async def cancel_rfq(
    project_id: UUID,
    rfq_id: UUID,
    payload: SourcingRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RequestForQuotation:
    return await _rfq_transition_route(project_id, rfq_id, payload, RFQStatus.CANCELLED, db, session)


@router.get("/projects/{project_id}/procurement/rfqs/{rfq_id}/quotations", response_model=list[QuotationRead])
async def list_quotations(
    project_id: UUID,
    rfq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[VendorQuotation]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(VendorQuotation)
        .where(
            VendorQuotation.organization_id == context.organization_id,
            VendorQuotation.project_id == project_id,
            VendorQuotation.rfq_id == rfq_id,
        )
        .order_by(VendorQuotation.created_at)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/rfqs/{rfq_id}/quotations",
    response_model=QuotationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_quotation_route(
    project_id: UUID,
    rfq_id: UUID,
    payload: QuotationCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorQuotation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await create_quotation(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            rfq_id=rfq_id,
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
    "/projects/{project_id}/procurement/quotations/{quotation_id}/lines",
    response_model=list[QuotationLineRead],
)
async def list_quotation_lines(
    project_id: UUID,
    quotation_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[VendorQuotationLine]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(VendorQuotationLine)
        .where(
            VendorQuotationLine.organization_id == context.organization_id,
            VendorQuotationLine.project_id == project_id,
            VendorQuotationLine.quotation_id == quotation_id,
        )
        .order_by(VendorQuotationLine.line_number)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/quotations/{quotation_id}/lines",
    response_model=QuotationLineRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_quotation_line_route(
    project_id: UUID,
    quotation_id: UUID,
    payload: QuotationLineCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorQuotationLine:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await add_quotation_line(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            quotation_id=quotation_id,
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


async def _quotation_transition_route(
    project_id: UUID,
    quotation_id: UUID,
    payload: SourcingRevisionAction,
    target: VendorQuotationStatus,
    db: DbSession,
    session: CurrentSession,
) -> VendorQuotation:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.manage")
    try:
        row = await transition_quotation(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            quotation_id=quotation_id,
            expected_revision=payload.expected_revision,
            target=target,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/procurement/quotations/{quotation_id}/submit", response_model=QuotationRead)
async def submit_quotation(
    project_id: UUID,
    quotation_id: UUID,
    payload: SourcingRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorQuotation:
    return await _quotation_transition_route(
        project_id,
        quotation_id,
        payload,
        VendorQuotationStatus.SUBMITTED,
        db,
        session,
    )


@router.post("/projects/{project_id}/procurement/quotations/{quotation_id}/withdraw", response_model=QuotationRead)
async def withdraw_quotation(
    project_id: UUID,
    quotation_id: UUID,
    payload: SourcingRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorQuotation:
    return await _quotation_transition_route(
        project_id,
        quotation_id,
        payload,
        VendorQuotationStatus.WITHDRAWN,
        db,
        session,
    )


@router.get("/projects/{project_id}/procurement/rfqs/{rfq_id}/comparison", response_model=RFQComparisonRead)
async def get_rfq_comparison(
    project_id: UUID,
    rfq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> dict[str, object]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    try:
        return await build_rfq_comparison(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            rfq_id=rfq_id,
        )
    except ProcurementValidationError as exc:
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/procurement/rfqs/{rfq_id}/selections",
    response_model=list[VendorSelectionRead],
)
async def list_vendor_selections(
    project_id: UUID,
    rfq_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[RFQVendorSelection]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    rows = await db.scalars(
        select(RFQVendorSelection)
        .where(
            RFQVendorSelection.organization_id == context.organization_id,
            RFQVendorSelection.project_id == project_id,
            RFQVendorSelection.rfq_id == rfq_id,
        )
        .order_by(RFQVendorSelection.selected_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/procurement/rfqs/{rfq_id}/select-vendor",
    response_model=VendorSelectionRead,
)
async def select_vendor_route(
    project_id: UUID,
    rfq_id: UUID,
    payload: VendorSelectionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> RFQVendorSelection:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.approve")
    try:
        row = await select_rfq_vendor(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            rfq_id=rfq_id,
            quotation_id=payload.quotation_id,
            expected_revision=payload.expected_revision,
            selected_by_membership_id=session.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/procurement/rfqs/{rfq_id}/purchase-order",
    response_model=PurchaseOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_po_from_selection_route(
    project_id: UUID,
    rfq_id: UUID,
    payload: PurchaseOrderFromSelectionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> PurchaseOrder:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.create")
    try:
        po, _source = await create_purchase_order_from_selection(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            rfq_id=rfq_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(po)
        return po
    except (ProcurementConflictError, ProcurementValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/source",
    response_model=PurchaseOrderSourceRead,
)
async def get_purchase_order_source(
    project_id: UUID,
    purchase_order_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> PurchaseOrderSource:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "procurement.purchase_order.view")
    row = await db.scalar(
        select(PurchaseOrderSource).where(
            PurchaseOrderSource.purchase_order_id == purchase_order_id,
            PurchaseOrderSource.project_id == project_id,
            PurchaseOrderSource.organization_id == context.organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order sourcing record not found")
    return row
