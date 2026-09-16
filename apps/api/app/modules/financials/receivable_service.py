from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import (
    BOQItem,
    ProjectPartyAssignment,
    ProjectPartyRole,
    RABill,
    RABillLine,
    RABillStatus,
)
from app.modules.events.service import enqueue_event
from app.modules.financials.models import (
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientReceipt,
    ClientReceiptAllocation,
    ClientReceiptStatus,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    _next_project_number,
    _require_project,
    _require_project_membership,
)


MONEY = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


async def _publish(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    entity_version: int,
    permission: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key=permission,
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": entity_version},
    )


async def invoice_received_amount(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    invoice_id: UUID,
) -> Decimal:
    amount = await db.scalar(
        select(func.coalesce(func.sum(ClientReceiptAllocation.amount), 0))
        .join(ClientReceipt, ClientReceipt.id == ClientReceiptAllocation.receipt_id)
        .where(
            ClientReceiptAllocation.organization_id == organization_id,
            ClientReceiptAllocation.project_id == project_id,
            ClientReceiptAllocation.invoice_id == invoice_id,
            ClientReceipt.status == ClientReceiptStatus.POSTED,
        )
    )
    return money(Decimal(amount or 0))


async def create_client_invoice_from_ra_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ClientInvoice:
    project = await _require_project(db, organization_id, project_id)
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    ra_bill_id = values.get("source_ra_bill_id")
    if not isinstance(ra_bill_id, UUID):
        raise FinancialValidationError("Certified RA bill is required")
    bill = await db.scalar(
        select(RABill)
        .where(
            RABill.id == ra_bill_id,
            RABill.organization_id == organization_id,
            RABill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise FinancialValidationError("RA bill was not found")
    if bill.status not in {RABillStatus.CERTIFIED, RABillStatus.PAID}:
        raise FinancialValidationError("Client invoice requires a certified RA bill")

    client_assignment = await db.scalar(
        select(ProjectPartyAssignment.id).where(
            ProjectPartyAssignment.organization_id == organization_id,
            ProjectPartyAssignment.project_id == project_id,
            ProjectPartyAssignment.party_id == bill.counterparty_id,
            ProjectPartyAssignment.role == ProjectPartyRole.CLIENT,
            ProjectPartyAssignment.active.is_(True),
        )
    )
    if client_assignment is None:
        raise FinancialValidationError("RA bill counterparty is not an active project client")

    existing = await db.scalar(
        select(ClientInvoice.id).where(
            ClientInvoice.organization_id == organization_id,
            ClientInvoice.project_id == project_id,
            ClientInvoice.source_ra_bill_id == ra_bill_id,
            ClientInvoice.status != ClientInvoiceStatus.CANCELLED,
        )
    )
    if existing is not None:
        raise FinancialConflictError("A client invoice already exists for this certified RA bill")

    project_currency = (project.currency_code or "INR").upper()
    if bill.currency_code.upper() != project_currency:
        raise FinancialValidationError("RA bill currency must match the project currency")

    invoice_date = values.get("invoice_date")
    due_date = values.get("due_date")
    if invoice_date is None:
        raise FinancialValidationError("Invoice date is required")
    if due_date is not None and due_date < invoice_date:
        raise FinancialValidationError("Invoice due date cannot be before invoice date")

    tax_rate = Decimal(str(values.get("tax_rate") or 0))
    if tax_rate < 0:
        raise FinancialValidationError("Tax rate cannot be negative")
    tax_code = str(values.get("tax_code") or "").strip().upper() or None
    withholding_amount = money(Decimal(str(values.get("withholding_amount") or 0)))
    if withholding_amount < 0:
        raise FinancialValidationError("Withholding amount cannot be negative")

    bill_lines = list(
        (
            await db.execute(
                select(RABillLine, BOQItem)
                .join(
                    BOQItem,
                    (BOQItem.id == RABillLine.boq_item_id)
                    & (BOQItem.project_id == RABillLine.project_id)
                    & (BOQItem.organization_id == RABillLine.organization_id),
                )
                .where(
                    RABillLine.organization_id == organization_id,
                    RABillLine.project_id == project_id,
                    RABillLine.ra_bill_id == ra_bill_id,
                )
                .order_by(BOQItem.line_number)
            )
        ).all()
    )
    if not bill_lines:
        raise FinancialValidationError("Certified RA bill has no bill lines")

    invoice_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="client_invoice",
        prefix="INV",
    )
    subtotal = money(sum((Decimal(line.gross_amount) for line, _item in bill_lines), Decimal(0)))
    tax_amount = money(subtotal * tax_rate / HUNDRED)
    total_amount = money(subtotal + tax_amount)
    if withholding_amount > total_amount:
        raise FinancialValidationError("Withholding amount cannot exceed invoice total")
    net_receivable = money(total_amount - withholding_amount)

    invoice = ClientInvoice(
        organization_id=organization_id,
        project_id=project_id,
        invoice_number=invoice_number,
        client_party_id=bill.counterparty_id,
        source_ra_bill_id=bill.id,
        invoice_date=invoice_date,
        due_date=due_date,
        currency_code=project_currency,
        subtotal=subtotal,
        tax_amount=tax_amount,
        withholding_amount=withholding_amount,
        total_amount=total_amount,
        net_receivable=net_receivable,
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(invoice)
    await db.flush()

    for line_number, (bill_line, item) in enumerate(bill_lines, start=1):
        amount = money(Decimal(bill_line.gross_amount))
        line_tax = money(amount * tax_rate / HUNDRED)
        db.add(
            ClientInvoiceLine(
                organization_id=organization_id,
                project_id=project_id,
                invoice_id=invoice.id,
                line_number=line_number,
                wbs_code_id=item.wbs_code_id,
                boq_item_id=item.id,
                description=item.description,
                unit_code=item.unit_code,
                quantity=bill_line.current_quantity,
                rate=bill_line.rate,
                amount=amount,
                hsn_sac=item.hsn_sac,
                tax_code=tax_code,
                tax_rate=tax_rate,
                tax_amount=line_tax,
            )
        )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.client_invoice.created_from_ra_bill",
        target_type="client_invoice",
        target_id=str(invoice.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "invoice_number": invoice.invoice_number,
            "source_ra_bill_id": str(bill.id),
            "client_party_id": str(invoice.client_party_id),
            "subtotal": str(invoice.subtotal),
            "tax_amount": str(invoice.tax_amount),
            "withholding_amount": str(invoice.withholding_amount),
            "net_receivable": str(invoice.net_receivable),
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="financials.client_invoice.created",
        entity_type="client_invoice",
        entity_id=invoice.id,
        entity_version=invoice.revision,
        permission="financials.receivable.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return invoice


async def transition_client_invoice(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    invoice_id: UUID,
    expected_revision: int,
    target_status: ClientInvoiceStatus,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ClientInvoice:
    invoice = await db.scalar(
        select(ClientInvoice)
        .where(
            ClientInvoice.id == invoice_id,
            ClientInvoice.organization_id == organization_id,
            ClientInvoice.project_id == project_id,
        )
        .with_for_update()
    )
    if invoice is None:
        raise FinancialValidationError("Client invoice was not found")
    if invoice.revision != expected_revision:
        raise FinancialConflictError("Client invoice changed; refresh before continuing")
    allowed = {
        ClientInvoiceStatus.DRAFT: {ClientInvoiceStatus.SUBMITTED, ClientInvoiceStatus.CANCELLED},
        ClientInvoiceStatus.SUBMITTED: {ClientInvoiceStatus.APPROVED, ClientInvoiceStatus.DRAFT, ClientInvoiceStatus.CANCELLED},
        ClientInvoiceStatus.APPROVED: {ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.CANCELLED},
    }
    if target_status not in allowed.get(invoice.status, set()):
        raise FinancialValidationError(
            f"Client invoice cannot move from {invoice.status.value} to {target_status.value}"
        )
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    now = datetime.now(UTC)
    if target_status == ClientInvoiceStatus.APPROVED:
        invoice.approved_by_membership_id = membership_id
        invoice.approved_at = now
    elif target_status == ClientInvoiceStatus.DRAFT:
        invoice.approved_by_membership_id = None
        invoice.approved_at = None
    elif target_status == ClientInvoiceStatus.ISSUED:
        invoice.issued_at = now
    invoice.status = target_status
    invoice.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"financials.client_invoice.{target_status.value}",
        target_type="client_invoice",
        target_id=str(invoice.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"status": invoice.status.value, "revision": invoice.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"financials.client_invoice.{target_status.value}",
        entity_type="client_invoice",
        entity_id=invoice.id,
        entity_version=invoice.revision,
        permission="financials.receivable.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return invoice


async def post_client_receipt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ClientReceipt:
    project = await _require_project(db, organization_id, project_id)
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    client_party_id = values.get("client_party_id")
    if not isinstance(client_party_id, UUID):
        raise FinancialValidationError("Client party is required")
    assignment = await db.scalar(
        select(ProjectPartyAssignment.id).where(
            ProjectPartyAssignment.organization_id == organization_id,
            ProjectPartyAssignment.project_id == project_id,
            ProjectPartyAssignment.party_id == client_party_id,
            ProjectPartyAssignment.role == ProjectPartyRole.CLIENT,
            ProjectPartyAssignment.active.is_(True),
        )
    )
    if assignment is None:
        raise FinancialValidationError("Active project client was not found")

    currency_code = str(values.get("currency_code") or project.currency_code or "INR").upper()
    if project.currency_code and currency_code != project.currency_code.upper():
        raise FinancialValidationError("Receipt currency must match the project currency")
    receipt_amount = money(Decimal(str(values.get("amount") or 0)))
    if receipt_amount <= 0:
        raise FinancialValidationError("Receipt amount must be greater than zero")
    allocations = values.get("allocations")
    if not isinstance(allocations, list) or not allocations:
        raise FinancialValidationError("Receipt requires at least one invoice allocation")
    allocation_total = money(
        sum((Decimal(str(item.get("amount") or 0)) for item in allocations if isinstance(item, Mapping)), Decimal(0))
    )
    if allocation_total != receipt_amount:
        raise FinancialValidationError("Receipt allocation total must equal receipt amount")

    invoice_ids = sorted(
        {item.get("invoice_id") for item in allocations if isinstance(item, Mapping) and isinstance(item.get("invoice_id"), UUID)},
        key=str,
    )
    if len(invoice_ids) != len(allocations):
        raise FinancialValidationError("Receipt allocations must contain unique valid invoice IDs")
    invoices = list(
        (
            await db.scalars(
                select(ClientInvoice)
                .where(
                    ClientInvoice.organization_id == organization_id,
                    ClientInvoice.project_id == project_id,
                    ClientInvoice.id.in_(invoice_ids),
                )
                .order_by(ClientInvoice.id)
                .with_for_update()
            )
        ).all()
    )
    if len(invoices) != len(invoice_ids):
        raise FinancialValidationError("One or more client invoices were not found")
    invoices_by_id = {invoice.id: invoice for invoice in invoices}

    normalized_allocations: list[tuple[ClientInvoice, Decimal]] = []
    for allocation in allocations:
        invoice = invoices_by_id[allocation["invoice_id"]]
        if invoice.client_party_id != client_party_id:
            raise FinancialValidationError("Receipt can only allocate invoices for the same client")
        if invoice.currency_code != currency_code:
            raise FinancialValidationError("Receipt and invoice currencies must match")
        if invoice.status not in {
            ClientInvoiceStatus.ISSUED,
            ClientInvoiceStatus.PARTIALLY_PAID,
        }:
            raise FinancialValidationError("Receipt can only allocate issued outstanding invoices")
        amount = money(Decimal(str(allocation.get("amount") or 0)))
        if amount <= 0:
            raise FinancialValidationError("Receipt allocation amount must be greater than zero")
        already_received = await invoice_received_amount(
            db,
            organization_id=organization_id,
            project_id=project_id,
            invoice_id=invoice.id,
        )
        outstanding = money(Decimal(invoice.net_receivable) - already_received)
        if amount > outstanding:
            raise FinancialValidationError(
                f"Receipt allocation exceeds outstanding amount for invoice {invoice.invoice_number}"
            )
        normalized_allocations.append((invoice, amount))

    receipt_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="client_receipt",
        prefix="REC",
    )
    now = datetime.now(UTC)
    receipt = ClientReceipt(
        organization_id=organization_id,
        project_id=project_id,
        receipt_number=receipt_number,
        client_party_id=client_party_id,
        receipt_date=values["receipt_date"],
        amount=receipt_amount,
        currency_code=currency_code,
        payment_method=values.get("payment_method") if isinstance(values.get("payment_method"), str) else None,
        payment_reference=values.get("payment_reference") if isinstance(values.get("payment_reference"), str) else None,
        status=ClientReceiptStatus.POSTED,
        posted_by_membership_id=membership_id,
        posted_at=now,
    )
    db.add(receipt)
    await db.flush()

    for invoice, amount in normalized_allocations:
        db.add(
            ClientReceiptAllocation(
                organization_id=organization_id,
                project_id=project_id,
                receipt_id=receipt.id,
                invoice_id=invoice.id,
                amount=amount,
            )
        )
    await db.flush()

    for invoice, _amount in normalized_allocations:
        received = await invoice_received_amount(
            db,
            organization_id=organization_id,
            project_id=project_id,
            invoice_id=invoice.id,
        )
        invoice.status = (
            ClientInvoiceStatus.PAID
            if received >= Decimal(invoice.net_receivable)
            else ClientInvoiceStatus.PARTIALLY_PAID
        )
        invoice.revision += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.client_receipt.posted",
        target_type="client_receipt",
        target_id=str(receipt.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "receipt_number": receipt.receipt_number,
            "client_party_id": str(client_party_id),
            "amount": str(receipt.amount),
            "allocation_count": len(normalized_allocations),
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="financials.client_receipt.posted",
        entity_type="client_receipt",
        entity_id=receipt.id,
        entity_version=1,
        permission="financials.receivable.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return receipt
