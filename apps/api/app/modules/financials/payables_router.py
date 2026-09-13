from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.payables_models import (
    VendorBill,
    VendorBillLine,
    VendorBillReceiptMatch,
)
from app.modules.financials.payables_schemas import (
    VendorBillCreate,
    VendorBillDetailRead,
    VendorBillLineCreate,
    VendorBillLineRead,
    VendorBillReceiptMatchRead,
    VendorBillTransition,
)
from app.modules.financials.payables_service import (
    VendorPayableConflictError,
    VendorPayableValidationError,
    add_vendor_bill_line,
    approve_vendor_bill,
    create_vendor_bill,
    delete_vendor_bill_line,
    reject_vendor_bill,
    submit_vendor_bill,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, VendorPayableConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    bill: VendorBill,
) -> VendorBillDetailRead:
    lines = list(
        (
            await db.scalars(
                select(VendorBillLine)
                .where(
                    VendorBillLine.organization_id == organization_id,
                    VendorBillLine.project_id == project_id,
                    VendorBillLine.vendor_bill_id == bill.id,
                )
                .order_by(VendorBillLine.line_number)
            )
        ).all()
    )
    line_reads: list[VendorBillLineRead] = []
    for line in lines:
        matches = list(
            (
                await db.scalars(
                    select(VendorBillReceiptMatch)
                    .where(
                        VendorBillReceiptMatch.organization_id == organization_id,
                        VendorBillReceiptMatch.project_id == project_id,
                        VendorBillReceiptMatch.vendor_bill_line_id == line.id,
                    )
                    .order_by(VendorBillReceiptMatch.created_at)
                )
            ).all()
        )
        line_reads.append(
            VendorBillLineRead(
                id=line.id,
                vendor_bill_id=line.vendor_bill_id,
                project_id=line.project_id,
                line_number=line.line_number,
                purchase_order_line_id=line.purchase_order_line_id,
                material_id=line.material_id,
                wbs_code_id=line.wbs_code_id,
                boq_item_id=line.boq_item_id,
                description=line.description,
                unit_code=line.unit_code,
                quantity=line.quantity,
                unit_price=line.unit_price,
                po_unit_price_snapshot=line.po_unit_price_snapshot,
                taxable_value=line.taxable_value,
                hsn_sac=line.hsn_sac,
                tax_code=line.tax_code,
                tax_rate=line.tax_rate,
                tax_amount=line.tax_amount,
                line_total=line.line_total,
                matched_quantity=line.matched_quantity,
                quantity_variance=line.quantity_variance,
                price_variance_amount=line.price_variance_amount,
                match_status=line.match_status,
                receipt_matches=[
                    VendorBillReceiptMatchRead.model_validate(match) for match in matches
                ],
            )
        )
    return VendorBillDetailRead(
        **VendorBillDetailRead.model_validate(bill).model_dump(exclude={"lines"}),
        lines=line_reads,
    )


@router.get(
    "/projects/{project_id}/financials/vendor-bills",
    response_model=list[VendorBillDetailRead],
)
async def list_vendor_bills(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[VendorBillDetailRead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.view")
    rows = list(
        (
            await db.scalars(
                select(VendorBill)
                .where(
                    VendorBill.organization_id == context.organization_id,
                    VendorBill.project_id == project_id,
                )
                .order_by(VendorBill.invoice_date.desc(), VendorBill.created_at.desc())
            )
        ).all()
    )
    return [
        await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=row,
        )
        for row in rows
    ]


@router.get(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}",
    response_model=VendorBillDetailRead,
)
async def get_vendor_bill(
    project_id: UUID,
    vendor_bill_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.view")
    row = await db.scalar(
        select(VendorBill).where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == context.organization_id,
            VendorBill.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor bill not found")
    return await _detail(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        bill=row,
    )


@router.post(
    "/projects/{project_id}/financials/vendor-bills",
    response_model=VendorBillDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vendor_bill_route(
    project_id: UUID,
    payload: VendorBillCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.create")
    try:
        row = await create_vendor_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=session.membership_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=row,
        )
    except (VendorPayableConflictError, VendorPayableValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/lines",
    response_model=VendorBillDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_vendor_bill_line_route(
    project_id: UUID,
    vendor_bill_id: UUID,
    payload: VendorBillLineCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.manage")
    try:
        line = await add_vendor_bill_line(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            vendor_bill_id=vendor_bill_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        bill = await db.get(VendorBill, line.vendor_bill_id)
        if bill is None:
            raise VendorPayableValidationError("Vendor bill was not found")
        await db.commit()
        await db.refresh(bill)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=bill,
        )
    except (VendorPayableConflictError, VendorPayableValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.delete(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/lines/{line_id}",
    response_model=VendorBillDetailRead,
)
async def delete_vendor_bill_line_route(
    project_id: UUID,
    vendor_bill_id: UUID,
    line_id: UUID,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.manage")
    try:
        bill = await delete_vendor_bill_line(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            vendor_bill_id=vendor_bill_id,
            line_id=line_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(bill)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=bill,
        )
    except (VendorPayableConflictError, VendorPayableValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/submit",
    response_model=VendorBillDetailRead,
)
async def submit_vendor_bill_route(
    project_id: UUID,
    vendor_bill_id: UUID,
    payload: VendorBillTransition,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.submit")
    if payload.allow_variance_override:
        _require_project_permission(context, project_id, "financials.payable.override")
    try:
        bill = await submit_vendor_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            vendor_bill_id=vendor_bill_id,
            membership_id=session.membership_id,
            expected_revision=payload.expected_revision,
            allow_variance_override=payload.allow_variance_override,
            reason=payload.reason,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(bill)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=bill,
        )
    except (VendorPayableConflictError, VendorPayableValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/approve",
    response_model=VendorBillDetailRead,
)
async def approve_vendor_bill_route(
    project_id: UUID,
    vendor_bill_id: UUID,
    payload: VendorBillTransition,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.approve")
    try:
        bill = await approve_vendor_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            vendor_bill_id=vendor_bill_id,
            membership_id=session.membership_id,
            expected_revision=payload.expected_revision,
            reason=payload.reason,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(bill)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=bill,
        )
    except (VendorPayableConflictError, VendorPayableValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/reject",
    response_model=VendorBillDetailRead,
)
async def reject_vendor_bill_route(
    project_id: UUID,
    vendor_bill_id: UUID,
    payload: VendorBillTransition,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> VendorBillDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.approve")
    try:
        bill = await reject_vendor_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            vendor_bill_id=vendor_bill_id,
            membership_id=session.membership_id,
            expected_revision=payload.expected_revision,
            reason=payload.reason,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(bill)
        return await _detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            bill=bill,
        )
    except (VendorPayableConflictError, VendorPayableValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
