from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.models import (
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientReceipt,
    ClientReceiptAllocation,
)
from app.modules.financials.receivable_schemas import (
    ClientInvoiceDetailRead,
    ClientInvoiceFromRABillCreate,
    ClientInvoiceLineRead,
    ClientInvoiceRead,
    ClientInvoiceRevisionAction,
    ClientReceiptAllocationRead,
    ClientReceiptCreate,
    ClientReceiptDetailRead,
    ClientReceiptRead,
    ClientReceiptReverseAction,
)
from app.modules.financials.receivable_service import (
    create_client_invoice_from_ra_bill,
    invoice_received_amount,
    post_client_receipt,
    reverse_client_receipt,
    transition_client_invoice,
)
from app.modules.financials.service import FinancialConflictError, FinancialValidationError
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, FinancialConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _invoice_detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    invoice: ClientInvoice,
) -> ClientInvoiceDetailRead:
    lines = list(
        (
            await db.scalars(
                select(ClientInvoiceLine)
                .where(
                    ClientInvoiceLine.organization_id == organization_id,
                    ClientInvoiceLine.project_id == project_id,
                    ClientInvoiceLine.invoice_id == invoice.id,
                )
                .order_by(ClientInvoiceLine.line_number)
            )
        ).all()
    )
    received = await invoice_received_amount(
        db,
        organization_id=organization_id,
        project_id=project_id,
        invoice_id=invoice.id,
    )
    outstanding = max(Decimal(invoice.net_receivable) - received, Decimal("0.00"))
    return ClientInvoiceDetailRead(
        **ClientInvoiceRead.model_validate(invoice).model_dump(),
        lines=[ClientInvoiceLineRead.model_validate(line) for line in lines],
        received_amount=received,
        outstanding_amount=outstanding,
    )


async def _receipt_detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    receipt: ClientReceipt,
) -> ClientReceiptDetailRead:
    allocations = list(
        (
            await db.scalars(
                select(ClientReceiptAllocation)
                .where(
                    ClientReceiptAllocation.organization_id == organization_id,
                    ClientReceiptAllocation.project_id == project_id,
                    ClientReceiptAllocation.receipt_id == receipt.id,
                )
                .order_by(ClientReceiptAllocation.created_at)
            )
        ).all()
    )
    return ClientReceiptDetailRead(
        **ClientReceiptRead.model_validate(receipt).model_dump(),
        allocations=[ClientReceiptAllocationRead.model_validate(row) for row in allocations],
    )


@router.get(
    "/projects/{project_id}/financials/receivables/invoices",
    response_model=list[ClientInvoiceRead],
)
async def list_client_invoices(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ClientInvoice]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.view")
    rows = await db.scalars(
        select(ClientInvoice)
        .where(
            ClientInvoice.organization_id == context.organization_id,
            ClientInvoice.project_id == project_id,
        )
        .order_by(ClientInvoice.invoice_date.desc(), ClientInvoice.created_at.desc())
    )
    return list(rows.all())


@router.get(
    "/projects/{project_id}/financials/receivables/invoices/{invoice_id}",
    response_model=ClientInvoiceDetailRead,
)
async def get_client_invoice(
    project_id: UUID,
    invoice_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> ClientInvoiceDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.view")
    row = await db.scalar(
        select(ClientInvoice).where(
            ClientInvoice.id == invoice_id,
            ClientInvoice.organization_id == context.organization_id,
            ClientInvoice.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client invoice not found")
    return await _invoice_detail(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        invoice=row,
    )


@router.post(
    "/projects/{project_id}/financials/receivables/invoices/from-ra-bill",
    response_model=ClientInvoiceDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_client_invoice_from_ra_bill_route(
    project_id: UUID,
    payload: ClientInvoiceFromRABillCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientInvoiceDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.manage")
    try:
        row = await create_client_invoice_from_ra_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return await _invoice_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            invoice=row,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


async def _transition_invoice_route(
    project_id: UUID,
    invoice_id: UUID,
    payload: ClientInvoiceRevisionAction,
    target: ClientInvoiceStatus,
    db: DbSession,
    session: CurrentSession,
) -> ClientInvoice:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.manage")
    try:
        row = await transition_client_invoice(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            invoice_id=invoice_id,
            expected_revision=payload.expected_revision,
            target_status=target,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post(
    "/projects/{project_id}/financials/receivables/invoices/{invoice_id}/submit",
    response_model=ClientInvoiceRead,
)
async def submit_client_invoice(
    project_id: UUID,
    invoice_id: UUID,
    payload: ClientInvoiceRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientInvoice:
    return await _transition_invoice_route(
        project_id, invoice_id, payload, ClientInvoiceStatus.SUBMITTED, db, session
    )


@router.post(
    "/projects/{project_id}/financials/receivables/invoices/{invoice_id}/approve",
    response_model=ClientInvoiceRead,
)
async def approve_client_invoice(
    project_id: UUID,
    invoice_id: UUID,
    payload: ClientInvoiceRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientInvoice:
    return await _transition_invoice_route(
        project_id, invoice_id, payload, ClientInvoiceStatus.APPROVED, db, session
    )


@router.post(
    "/projects/{project_id}/financials/receivables/invoices/{invoice_id}/issue",
    response_model=ClientInvoiceRead,
)
async def issue_client_invoice(
    project_id: UUID,
    invoice_id: UUID,
    payload: ClientInvoiceRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientInvoice:
    return await _transition_invoice_route(
        project_id, invoice_id, payload, ClientInvoiceStatus.ISSUED, db, session
    )


@router.post(
    "/projects/{project_id}/financials/receivables/invoices/{invoice_id}/cancel",
    response_model=ClientInvoiceRead,
)
async def cancel_client_invoice(
    project_id: UUID,
    invoice_id: UUID,
    payload: ClientInvoiceRevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientInvoice:
    return await _transition_invoice_route(
        project_id, invoice_id, payload, ClientInvoiceStatus.CANCELLED, db, session
    )


@router.get(
    "/projects/{project_id}/financials/receivables/receipts",
    response_model=list[ClientReceiptRead],
)
async def list_client_receipts(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ClientReceipt]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.view")
    rows = await db.scalars(
        select(ClientReceipt)
        .where(
            ClientReceipt.organization_id == context.organization_id,
            ClientReceipt.project_id == project_id,
        )
        .order_by(ClientReceipt.receipt_date.desc(), ClientReceipt.created_at.desc())
    )
    return list(rows.all())


@router.get(
    "/projects/{project_id}/financials/receivables/receipts/{receipt_id}",
    response_model=ClientReceiptDetailRead,
)
async def get_client_receipt(
    project_id: UUID,
    receipt_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> ClientReceiptDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.view")
    row = await db.scalar(
        select(ClientReceipt).where(
            ClientReceipt.id == receipt_id,
            ClientReceipt.organization_id == context.organization_id,
            ClientReceipt.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client receipt not found")
    return await _receipt_detail(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        receipt=row,
    )


@router.post(
    "/projects/{project_id}/financials/receivables/receipts",
    response_model=ClientReceiptDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_client_receipt_route(
    project_id: UUID,
    payload: ClientReceiptCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientReceiptDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receipt.post")
    try:
        row = await post_client_receipt(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return await _receipt_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            receipt=row,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)



@router.post(
    "/projects/{project_id}/financials/receivables/receipts/{receipt_id}/reverse",
    response_model=ClientReceiptDetailRead,
)
async def reverse_client_receipt_route(
    project_id: UUID,
    receipt_id: UUID,
    payload: ClientReceiptReverseAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientReceiptDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receipt.reverse")
    try:
        row = await reverse_client_receipt(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            receipt_id=receipt_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            reason=payload.reason,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return await _receipt_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            receipt=row,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
