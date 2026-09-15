from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import Party, PartyStatus, PartyType
from app.modules.procurement.models import (
    PurchaseOrder,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RequisitionStatus,
)
from app.modules.procurement.service import (
    HUNDRED,
    ProcurementConflictError,
    ProcurementValidationError,
    _publish,
    _require_project_membership,
    add_purchase_order_line,
    create_purchase_order,
    money,
)
from app.modules.procurement.sourcing_models import (
    ProcurementSourcingCounter,
    PurchaseOrderSource,
    RFQInvitationStatus,
    RFQStatus,
    RFQVendorInvitation,
    RFQVendorSelection,
    RequestForQuotation,
    RequestForQuotationLine,
    VendorQuotation,
    VendorQuotationLine,
    VendorQuotationStatus,
)


async def allocate_sourcing_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    kind: str,
) -> int:
    columns = {
        "rfq": ProcurementSourcingCounter.next_rfq_number,
        "quote": ProcurementSourcingCounter.next_quote_number,
    }
    column = columns.get(kind)
    if column is None:
        raise ValueError(f"Unknown sourcing counter kind: {kind}")
    values = {
        "project_id": project_id,
        "organization_id": organization_id,
        "next_rfq_number": 1,
        "next_quote_number": 1,
    }
    values[column.key] = 2
    statement = (
        insert(ProcurementSourcingCounter)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[ProcurementSourcingCounter.project_id],
            set_={column.key: column + 1},
            where=ProcurementSourcingCounter.organization_id == organization_id,
        )
        .returning(column)
    )
    next_number = await db.scalar(statement)
    if next_number is None:
        raise ProcurementValidationError("Sourcing counter does not belong to this company")
    return next_number - 1


def _json_safe(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


async def create_rfq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> RequestForQuotation:
    requisition_id = values.get("requisition_id")
    if not isinstance(requisition_id, UUID):
        raise ProcurementValidationError("Approved requisition is required")
    requisition = await db.scalar(
        select(PurchaseRequisition).where(
            PurchaseRequisition.id == requisition_id,
            PurchaseRequisition.project_id == project_id,
            PurchaseRequisition.organization_id == organization_id,
        )
    )
    if requisition is None or requisition.status != RequisitionStatus.APPROVED:
        raise ProcurementValidationError("RFQ requires an approved requisition")

    title = str(values.get("title") or "").strip()
    if not title:
        raise ProcurementValidationError("RFQ title is required")

    requested_line_ids = values.get("requisition_line_ids")
    line_query = select(PurchaseRequisitionLine).where(
        PurchaseRequisitionLine.requisition_id == requisition_id,
        PurchaseRequisitionLine.project_id == project_id,
        PurchaseRequisitionLine.organization_id == organization_id,
    )
    if isinstance(requested_line_ids, list) and requested_line_ids:
        unique_line_ids = {item for item in requested_line_ids if isinstance(item, UUID)}
        line_query = line_query.where(PurchaseRequisitionLine.id.in_(unique_line_ids))
    source_lines = list((await db.scalars(line_query.order_by(PurchaseRequisitionLine.line_number))).all())
    if not source_lines:
        raise ProcurementValidationError("RFQ must contain at least one approved requisition line")
    if isinstance(requested_line_ids, list) and requested_line_ids:
        requested_count = len({item for item in requested_line_ids if isinstance(item, UUID)})
        if requested_count != len(source_lines):
            raise ProcurementValidationError("One or more requisition lines were not found in the approved requisition")

    number = await allocate_sourcing_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="rfq",
    )
    row = RequestForQuotation(
        organization_id=organization_id,
        project_id=project_id,
        requisition_id=requisition_id,
        number=f"RFQ-{number:05d}",
        title=title,
        due_at=values.get("due_at"),
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(row)
    await db.flush()
    for source in source_lines:
        db.add(
            RequestForQuotationLine(
                organization_id=organization_id,
                project_id=project_id,
                rfq_id=row.id,
                requisition_line_id=source.id,
                line_number=source.line_number,
                material_id=source.material_id,
                wbs_code_id=source.wbs_code_id,
                boq_item_id=source.boq_item_id,
                description=source.description,
                unit_code=source.unit_code,
                quantity=source.quantity,
                notes=source.notes,
            )
        )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.rfq.created",
        target_type="procurement_rfq",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"number": row.number, "requisition_id": str(requisition_id), "line_count": len(source_lines)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.rfq.created",
        entity_type="procurement_rfq",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def invite_rfq_vendor(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfq_id: UUID,
    supplier_party_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    notes: str | None = None,
) -> RFQVendorInvitation:
    rfq = await db.scalar(
        select(RequestForQuotation)
        .where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.project_id == project_id,
            RequestForQuotation.organization_id == organization_id,
        )
        .with_for_update()
    )
    if rfq is None:
        raise ProcurementValidationError("RFQ was not found")
    if rfq.status != RFQStatus.DRAFT:
        raise ProcurementValidationError("Vendors can only be invited while the RFQ is draft")
    supplier = await db.scalar(
        select(Party).where(
            Party.id == supplier_party_id,
            Party.organization_id == organization_id,
        )
    )
    if supplier is None or supplier.status != PartyStatus.ACTIVE or supplier.party_type != PartyType.SUPPLIER:
        raise ProcurementValidationError("Active supplier party was not found")
    existing = await db.scalar(
        select(RFQVendorInvitation.id).where(
            RFQVendorInvitation.rfq_id == rfq_id,
            RFQVendorInvitation.supplier_party_id == supplier_party_id,
        )
    )
    if existing is not None:
        raise ProcurementConflictError("Supplier is already invited to this RFQ")

    row = RFQVendorInvitation(
        organization_id=organization_id,
        project_id=project_id,
        rfq_id=rfq_id,
        supplier_party_id=supplier_party_id,
        invited_at=datetime.now(UTC),
        notes=notes,
    )
    db.add(row)
    rfq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.rfq.vendor_invited",
        target_type="procurement_rfq",
        target_id=str(rfq.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"supplier_party_id": str(supplier_party_id), "revision": rfq.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.rfq.updated",
        entity_type="procurement_rfq",
        entity_id=rfq.id,
        entity_version=rfq.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def transition_rfq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfq_id: UUID,
    expected_revision: int,
    target: RFQStatus,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> RequestForQuotation:
    row = await db.scalar(
        select(RequestForQuotation)
        .where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.project_id == project_id,
            RequestForQuotation.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ProcurementValidationError("RFQ was not found")
    if row.revision != expected_revision:
        raise ProcurementConflictError("RFQ changed; refresh before continuing")
    allowed = {
        RFQStatus.DRAFT: {RFQStatus.ISSUED, RFQStatus.CANCELLED},
        RFQStatus.ISSUED: {RFQStatus.CLOSED, RFQStatus.CANCELLED},
    }
    if target not in allowed.get(row.status, set()):
        raise ProcurementValidationError(f"RFQ cannot move from {row.status.value} to {target.value}")
    if target == RFQStatus.ISSUED:
        vendor_count = await db.scalar(
            select(func.count(RFQVendorInvitation.id)).where(RFQVendorInvitation.rfq_id == row.id)
        )
        if not vendor_count:
            raise ProcurementValidationError("Invite at least one supplier before issuing the RFQ")
        row.issued_at = datetime.now(UTC)
    if target in {RFQStatus.CLOSED, RFQStatus.CANCELLED}:
        row.closed_at = datetime.now(UTC)
    row.status = target
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"procurement.rfq.{target.value}",
        target_type="procurement_rfq",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if target == RFQStatus.ISSUED else AuditRisk.HIGH,
        reason=reason,
        changes={"status": target.value, "revision": row.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"procurement.rfq.{target.value}",
        entity_type="procurement_rfq",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def create_quotation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfq_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorQuotation:
    rfq = await db.scalar(
        select(RequestForQuotation).where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.project_id == project_id,
            RequestForQuotation.organization_id == organization_id,
        )
    )
    if rfq is None or rfq.status != RFQStatus.ISSUED:
        raise ProcurementValidationError("Quotation requires an issued RFQ")
    supplier_party_id = values.get("supplier_party_id")
    if not isinstance(supplier_party_id, UUID):
        raise ProcurementValidationError("Supplier is required")
    invitation = await db.scalar(
        select(RFQVendorInvitation).where(
            RFQVendorInvitation.rfq_id == rfq_id,
            RFQVendorInvitation.supplier_party_id == supplier_party_id,
            RFQVendorInvitation.organization_id == organization_id,
        )
    )
    if invitation is None:
        raise ProcurementValidationError("Supplier was not invited to this RFQ")
    existing = await db.scalar(
        select(VendorQuotation.id).where(
            VendorQuotation.rfq_id == rfq_id,
            VendorQuotation.supplier_party_id == supplier_party_id,
        )
    )
    if existing is not None:
        raise ProcurementConflictError("A quotation already exists for this supplier and RFQ")
    quote_date = values.get("quote_date")
    valid_until = values.get("valid_until")
    if quote_date is None:
        raise ProcurementValidationError("Quotation date is required")
    if valid_until is not None and valid_until < quote_date:
        raise ProcurementValidationError("Quotation valid-until date cannot be before quotation date")

    number = await allocate_sourcing_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="quote",
    )
    row = VendorQuotation(
        organization_id=organization_id,
        project_id=project_id,
        rfq_id=rfq_id,
        supplier_party_id=supplier_party_id,
        number=f"VQ-{number:05d}",
        supplier_reference=values.get("supplier_reference"),
        quote_date=quote_date,
        valid_until=valid_until,
        currency_code=str(values.get("currency_code") or "INR").upper(),
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.quotation.created",
        target_type="vendor_quotation",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"rfq_id": str(rfq_id), "supplier_party_id": str(supplier_party_id), "number": row.number},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.quotation.created",
        entity_type="vendor_quotation",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def _recalculate_quotation(db: AsyncSession, quotation: VendorQuotation) -> None:
    totals = await db.execute(
        select(
            func.coalesce(func.sum(VendorQuotationLine.taxable_value), 0),
            func.coalesce(func.sum(VendorQuotationLine.tax_amount), 0),
            func.coalesce(func.sum(VendorQuotationLine.line_total), 0),
        ).where(VendorQuotationLine.quotation_id == quotation.id)
    )
    subtotal, tax_total, total = totals.one()
    quotation.subtotal = money(Decimal(subtotal))
    quotation.tax_total = money(Decimal(tax_total))
    quotation.total = money(Decimal(total))


async def add_quotation_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    quotation_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> VendorQuotationLine:
    quotation = await db.scalar(
        select(VendorQuotation)
        .where(
            VendorQuotation.id == quotation_id,
            VendorQuotation.project_id == project_id,
            VendorQuotation.organization_id == organization_id,
        )
        .with_for_update()
    )
    if quotation is None:
        raise ProcurementValidationError("Quotation was not found")
    if quotation.status != VendorQuotationStatus.DRAFT:
        raise ProcurementValidationError("Only draft quotations can be edited")
    rfq_line_id = values.get("rfq_line_id")
    if not isinstance(rfq_line_id, UUID):
        raise ProcurementValidationError("RFQ line is required")
    rfq_line = await db.scalar(
        select(RequestForQuotationLine).where(
            RequestForQuotationLine.id == rfq_line_id,
            RequestForQuotationLine.rfq_id == quotation.rfq_id,
            RequestForQuotationLine.project_id == project_id,
            RequestForQuotationLine.organization_id == organization_id,
        )
    )
    if rfq_line is None:
        raise ProcurementValidationError("RFQ line was not found for this quotation")
    quantity = Decimal(values.get("quantity") or 0)
    if quantity <= 0 or quantity > rfq_line.quantity:
        raise ProcurementValidationError("Quoted quantity must be greater than zero and cannot exceed RFQ quantity")
    unit_price = money(Decimal(values.get("unit_price") or 0))
    tax_rate_raw = values.get("tax_rate")
    tax_rate = Decimal(tax_rate_raw) if tax_rate_raw is not None else None
    taxable_value = money(quantity * unit_price)
    tax_amount = money(taxable_value * tax_rate / HUNDRED) if tax_rate is not None else Decimal(0)
    line = VendorQuotationLine(
        organization_id=organization_id,
        project_id=project_id,
        quotation_id=quotation_id,
        rfq_line_id=rfq_line_id,
        line_number=int(values.get("line_number") or rfq_line.line_number),
        quantity=quantity,
        unit_code=rfq_line.unit_code,
        unit_price=unit_price,
        taxable_value=taxable_value,
        hsn_sac=values.get("hsn_sac"),
        tax_code=values.get("tax_code"),
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        line_total=money(taxable_value + tax_amount),
        lead_time_days=values.get("lead_time_days"),
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(line)
    await db.flush()
    await _recalculate_quotation(db, quotation)
    quotation.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.quotation_line.created",
        target_type="vendor_quotation_line",
        target_id=str(line.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"quotation_id": str(quotation.id), "line_total": str(line.line_total)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.quotation.updated",
        entity_type="vendor_quotation",
        entity_id=quotation.id,
        entity_version=quotation.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return line


async def transition_quotation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    quotation_id: UUID,
    expected_revision: int,
    target: VendorQuotationStatus,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> VendorQuotation:
    row = await db.scalar(
        select(VendorQuotation)
        .where(
            VendorQuotation.id == quotation_id,
            VendorQuotation.project_id == project_id,
            VendorQuotation.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ProcurementValidationError("Quotation was not found")
    if row.revision != expected_revision:
        raise ProcurementConflictError("Quotation changed; refresh before continuing")
    allowed = {
        VendorQuotationStatus.DRAFT: {VendorQuotationStatus.SUBMITTED},
        VendorQuotationStatus.SUBMITTED: {VendorQuotationStatus.WITHDRAWN},
    }
    if target not in allowed.get(row.status, set()):
        raise ProcurementValidationError(
            f"Quotation cannot move from {row.status.value} to {target.value}"
        )
    now = datetime.now(UTC)
    if target == VendorQuotationStatus.SUBMITTED:
        line_count = await db.scalar(
            select(func.count(VendorQuotationLine.id)).where(VendorQuotationLine.quotation_id == row.id)
        )
        if not line_count:
            raise ProcurementValidationError("A quotation with no lines cannot be submitted")
        row.submitted_at = now
        invitation = await db.scalar(
            select(RFQVendorInvitation).where(
                RFQVendorInvitation.rfq_id == row.rfq_id,
                RFQVendorInvitation.supplier_party_id == row.supplier_party_id,
            )
        )
        if invitation is not None:
            invitation.status = RFQInvitationStatus.QUOTED
            invitation.responded_at = now
    if target == VendorQuotationStatus.WITHDRAWN:
        row.withdrawn_at = now
    row.status = target
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"procurement.quotation.{target.value}",
        target_type="vendor_quotation",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if target == VendorQuotationStatus.SUBMITTED else AuditRisk.HIGH,
        reason=reason,
        changes={"status": target.value, "revision": row.revision, "total": str(row.total)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"procurement.quotation.{target.value}",
        entity_type="vendor_quotation",
        entity_id=row.id,
        entity_version=row.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def build_rfq_comparison(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfq_id: UUID,
) -> dict[str, object]:
    rfq = await db.scalar(
        select(RequestForQuotation).where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.project_id == project_id,
            RequestForQuotation.organization_id == organization_id,
        )
    )
    if rfq is None:
        raise ProcurementValidationError("RFQ was not found")
    rfq_lines = list(
        (
            await db.scalars(
                select(RequestForQuotationLine)
                .where(RequestForQuotationLine.rfq_id == rfq_id)
                .order_by(RequestForQuotationLine.line_number)
            )
        ).all()
    )
    quotations = list(
        (
            await db.scalars(
                select(VendorQuotation)
                .where(
                    VendorQuotation.rfq_id == rfq_id,
                    VendorQuotation.status == VendorQuotationStatus.SUBMITTED,
                )
                .order_by(VendorQuotation.total, VendorQuotation.number)
            )
        ).all()
    )
    quotation_ids = [item.id for item in quotations]
    quote_lines = []
    if quotation_ids:
        quote_lines = list(
            (
                await db.scalars(
                    select(VendorQuotationLine)
                    .where(VendorQuotationLine.quotation_id.in_(quotation_ids))
                    .order_by(VendorQuotationLine.line_number)
                )
            ).all()
        )
    quote_by_id = {item.id: item for item in quotations}
    offers_by_line: dict[UUID, list[dict[str, object]]] = {item.id: [] for item in rfq_lines}
    coverage: dict[UUID, set[UUID]] = {item.id: set() for item in quotations}
    for line in quote_lines:
        quote = quote_by_id[line.quotation_id]
        coverage[quote.id].add(line.rfq_line_id)
        offers_by_line.setdefault(line.rfq_line_id, []).append(
            {
                "quotation_id": quote.id,
                "supplier_party_id": quote.supplier_party_id,
                "quotation_number": quote.number,
                "currency_code": quote.currency_code,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "tax_rate": line.tax_rate,
                "line_total": line.line_total,
                "lead_time_days": line.lead_time_days,
            }
        )
    comparison_lines = [
        {
            "rfq_line_id": line.id,
            "line_number": line.line_number,
            "description": line.description,
            "unit_code": line.unit_code,
            "required_quantity": line.quantity,
            "offers": sorted(
                offers_by_line.get(line.id, []),
                key=lambda offer: (str(offer["currency_code"]), Decimal(offer["line_total"])),
            ),
        }
        for line in rfq_lines
    ]
    summaries = [
        {
            "quotation_id": quote.id,
            "supplier_party_id": quote.supplier_party_id,
            "quotation_number": quote.number,
            "currency_code": quote.currency_code,
            "subtotal": quote.subtotal,
            "tax_total": quote.tax_total,
            "total": quote.total,
            "covered_lines": len(coverage.get(quote.id, set())),
            "required_lines": len(rfq_lines),
            "complete": len(coverage.get(quote.id, set())) == len(rfq_lines),
        }
        for quote in quotations
    ]
    return {
        "rfq_id": rfq.id,
        "rfq_number": rfq.number,
        "rfq_revision": rfq.revision,
        "lines": comparison_lines,
        "quotations": summaries,
    }


async def select_rfq_vendor(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfq_id: UUID,
    quotation_id: UUID,
    expected_revision: int,
    selected_by_membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> RFQVendorSelection:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=selected_by_membership_id,
    )
    rfq = await db.scalar(
        select(RequestForQuotation)
        .where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.project_id == project_id,
            RequestForQuotation.organization_id == organization_id,
        )
        .with_for_update()
    )
    if rfq is None:
        raise ProcurementValidationError("RFQ was not found")
    if rfq.revision != expected_revision:
        raise ProcurementConflictError("RFQ changed; refresh before selecting a vendor")
    if rfq.status not in {RFQStatus.ISSUED, RFQStatus.CLOSED}:
        raise ProcurementValidationError("Vendor can only be selected for an issued RFQ")
    quotation = await db.scalar(
        select(VendorQuotation).where(
            VendorQuotation.id == quotation_id,
            VendorQuotation.rfq_id == rfq_id,
            VendorQuotation.project_id == project_id,
            VendorQuotation.organization_id == organization_id,
            VendorQuotation.status == VendorQuotationStatus.SUBMITTED,
        )
    )
    if quotation is None:
        raise ProcurementValidationError("Submitted quotation was not found for this RFQ")

    comparison = await build_rfq_comparison(
        db,
        organization_id=organization_id,
        project_id=project_id,
        rfq_id=rfq_id,
    )
    summaries = comparison["quotations"]
    selected_summary = next(
        (item for item in summaries if item["quotation_id"] == quotation_id),
        None,
    )
    if selected_summary is None:
        raise ProcurementValidationError("Selected quotation is not available in the comparison")
    submitted_currencies = {str(item["currency_code"]) for item in summaries}
    comparable = [
        item
        for item in summaries
        if item["complete"] and item["currency_code"] == selected_summary["currency_code"]
    ]
    lowest = min(comparable, key=lambda item: Decimal(item["total"])) if comparable else None
    explanation_required = (
        len(submitted_currencies) > 1
        or not selected_summary["complete"]
        or (lowest is not None and lowest["quotation_id"] != quotation_id)
    )
    if explanation_required and not (reason or "").strip():
        raise ProcurementValidationError(
            "Selection reason is required when the chosen quotation is not the lowest complete comparable offer"
        )

    current = await db.scalar(
        select(RFQVendorSelection)
        .where(
            RFQVendorSelection.rfq_id == rfq_id,
            RFQVendorSelection.superseded_at.is_(None),
        )
        .order_by(RFQVendorSelection.selected_at.desc())
        .with_for_update()
    )
    if current is not None:
        po_source = await db.scalar(
            select(PurchaseOrderSource.id).where(PurchaseOrderSource.selection_id == current.id)
        )
        if po_source is not None:
            raise ProcurementConflictError("Vendor selection cannot change after a purchase order is created")
        current.superseded_at = datetime.now(UTC)

    now = datetime.now(UTC)
    row = RFQVendorSelection(
        organization_id=organization_id,
        project_id=project_id,
        rfq_id=rfq_id,
        quotation_id=quotation.id,
        supplier_party_id=quotation.supplier_party_id,
        selected_by_membership_id=selected_by_membership_id,
        selected_at=now,
        reason=(reason or "").strip() or None,
        comparison_snapshot=_json_safe(comparison),
        supersedes_selection_id=current.id if current is not None else None,
    )
    db.add(row)
    rfq.status = RFQStatus.CLOSED
    rfq.closed_at = now
    rfq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.rfq.vendor_selected",
        target_type="procurement_rfq_vendor_selection",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=row.reason,
        changes={
            "rfq_id": str(rfq_id),
            "quotation_id": str(quotation.id),
            "supplier_party_id": str(quotation.supplier_party_id),
            "rfq_revision": rfq.revision,
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.rfq.vendor_selected",
        entity_type="procurement_rfq",
        entity_id=rfq.id,
        entity_version=rfq.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def create_purchase_order_from_selection(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    rfq_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> tuple[PurchaseOrder, PurchaseOrderSource]:
    selection = await db.scalar(
        select(RFQVendorSelection)
        .where(
            RFQVendorSelection.rfq_id == rfq_id,
            RFQVendorSelection.project_id == project_id,
            RFQVendorSelection.organization_id == organization_id,
            RFQVendorSelection.superseded_at.is_(None),
        )
        .order_by(RFQVendorSelection.selected_at.desc())
        .with_for_update()
    )
    if selection is None:
        raise ProcurementValidationError("Select a vendor before creating the purchase order")
    existing_source = await db.scalar(
        select(PurchaseOrderSource).where(PurchaseOrderSource.selection_id == selection.id)
    )
    if existing_source is not None:
        existing_po = await db.scalar(
            select(PurchaseOrder).where(PurchaseOrder.id == existing_source.purchase_order_id)
        )
        if existing_po is None:
            raise ProcurementConflictError("Purchase order source exists without its purchase order")
        return existing_po, existing_source

    rfq = await db.scalar(
        select(RequestForQuotation).where(
            RequestForQuotation.id == rfq_id,
            RequestForQuotation.project_id == project_id,
            RequestForQuotation.organization_id == organization_id,
        )
    )
    quotation = await db.scalar(
        select(VendorQuotation).where(
            VendorQuotation.id == selection.quotation_id,
            VendorQuotation.status == VendorQuotationStatus.SUBMITTED,
        )
    )
    if rfq is None or quotation is None:
        raise ProcurementValidationError("Selected RFQ quotation is no longer available")
    quote_lines = list(
        (
            await db.scalars(
                select(VendorQuotationLine)
                .where(VendorQuotationLine.quotation_id == quotation.id)
                .order_by(VendorQuotationLine.line_number)
            )
        ).all()
    )
    if not quote_lines:
        raise ProcurementValidationError("Selected quotation has no lines")
    rfq_line_ids = [line.rfq_line_id for line in quote_lines]
    rfq_lines = list(
        (
            await db.scalars(
                select(RequestForQuotationLine).where(RequestForQuotationLine.id.in_(rfq_line_ids))
            )
        ).all()
    )
    rfq_line_by_id = {line.id: line for line in rfq_lines}
    if len(rfq_line_by_id) != len(set(rfq_line_ids)):
        raise ProcurementValidationError("Selected quotation contains an invalid RFQ line")

    po = await create_purchase_order(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values={
            "supplier_party_id": quotation.supplier_party_id,
            "requisition_id": rfq.requisition_id,
            "order_date": values["order_date"],
            "expected_delivery_date": values.get("expected_delivery_date"),
            "currency_code": quotation.currency_code,
            "notes": values.get("notes") or f"Created from {rfq.number} / {quotation.number}",
        },
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    for quote_line in quote_lines:
        rfq_line = rfq_line_by_id[quote_line.rfq_line_id]
        await add_purchase_order_line(
            db,
            organization_id=organization_id,
            project_id=project_id,
            purchase_order_id=po.id,
            values={
                "line_number": quote_line.line_number,
                "requisition_line_id": rfq_line.requisition_line_id,
                "material_id": rfq_line.material_id,
                "wbs_code_id": rfq_line.wbs_code_id,
                "description": rfq_line.description,
                "unit_code": rfq_line.unit_code,
                "quantity": quote_line.quantity,
                "unit_price": quote_line.unit_price,
                "hsn_sac": quote_line.hsn_sac,
                "tax_code": quote_line.tax_code,
                "tax_rate": quote_line.tax_rate,
                "notes": quote_line.notes,
            },
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    source = PurchaseOrderSource(
        organization_id=organization_id,
        project_id=project_id,
        purchase_order_id=po.id,
        rfq_id=rfq.id,
        quotation_id=quotation.id,
        selection_id=selection.id,
    )
    db.add(source)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.rfq.selection_converted_to_po",
        target_type="purchase_order",
        target_id=str(po.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "rfq_id": str(rfq.id),
            "quotation_id": str(quotation.id),
            "selection_id": str(selection.id),
            "purchase_order_number": po.number,
        },
    )
    return po, source
