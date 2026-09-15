from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.financials.commitment_models import ProjectCommitmentAllocation
from app.modules.financials.models import (
    CommitmentSourceType,
    CommitmentStatus,
    ProjectCommitment,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    _require_project,
    _require_project_membership,
)
from app.modules.procurement.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseRequisitionLine,
)
from app.modules.search.service import schedule_search_index


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def post_purchase_order_commitment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectCommitment:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    project = await _require_project(db, organization_id, project_id)

    existing = await db.scalar(
        select(ProjectCommitment).where(
            ProjectCommitment.organization_id == organization_id,
            ProjectCommitment.project_id == project_id,
            ProjectCommitment.source_type == CommitmentSourceType.PURCHASE_ORDER,
            ProjectCommitment.source_id == purchase_order_id,
        )
    )
    if existing is not None:
        return existing

    purchase_order = await db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.project_id == project_id,
        )
    )
    if purchase_order is None:
        raise FinancialValidationError("Purchase order was not found in this project")
    if purchase_order.status not in {
        PurchaseOrderStatus.ISSUED,
        PurchaseOrderStatus.PART_RECEIVED,
        PurchaseOrderStatus.CLOSED,
    }:
        raise FinancialValidationError(
            "Only an issued purchase order can create a project commitment"
        )
    if purchase_order.issued_at is None:
        raise FinancialValidationError(
            "Issued purchase order is missing its authoritative issued timestamp"
        )

    project_currency = (project.currency_code or "INR").upper()
    if purchase_order.currency_code.upper() != project_currency:
        raise FinancialValidationError(
            "Purchase order currency must match project currency before commitment posting"
        )

    lines = list(
        (
            await db.scalars(
                select(PurchaseOrderLine)
                .where(
                    PurchaseOrderLine.organization_id == organization_id,
                    PurchaseOrderLine.project_id == project_id,
                    PurchaseOrderLine.purchase_order_id == purchase_order.id,
                )
                .order_by(PurchaseOrderLine.line_number)
            )
        ).all()
    )
    if not lines:
        raise FinancialValidationError("Issued purchase order has no lines")

    net_total = _money(sum((line.taxable_value for line in lines), start=Decimal(0)))
    tax_total = _money(sum((line.tax_amount for line in lines), start=Decimal(0)))
    gross_total = _money(sum((line.line_total for line in lines), start=Decimal(0)))
    if (
        net_total != purchase_order.subtotal
        or tax_total != purchase_order.tax_total
        or gross_total != purchase_order.total
    ):
        raise FinancialConflictError(
            "Purchase order header totals do not reconcile to its authoritative lines"
        )
    if net_total <= 0:
        raise FinancialValidationError(
            "Purchase order must have a positive tax-exclusive value before commitment posting"
        )

    requisition_line_ids = {
        line.requisition_line_id
        for line in lines
        if line.requisition_line_id is not None
    }
    requisition_lines: dict[UUID, PurchaseRequisitionLine] = {}
    if requisition_line_ids:
        rows = await db.scalars(
            select(PurchaseRequisitionLine).where(
                PurchaseRequisitionLine.organization_id == organization_id,
                PurchaseRequisitionLine.project_id == project_id,
                PurchaseRequisitionLine.id.in_(requisition_line_ids),
            )
        )
        requisition_lines = {row.id: row for row in rows.all()}

    wbs_values = [line.wbs_code_id for line in lines]
    common_wbs_id = None
    if wbs_values and all(value is not None for value in wbs_values):
        distinct_wbs = set(wbs_values)
        if len(distinct_wbs) == 1:
            common_wbs_id = next(iter(distinct_wbs))

    commitment = ProjectCommitment(
        organization_id=organization_id,
        project_id=project_id,
        source_type=CommitmentSourceType.PURCHASE_ORDER,
        source_id=purchase_order.id,
        source_number=purchase_order.number,
        party_id=purchase_order.supplier_party_id,
        wbs_code_id=common_wbs_id,
        committed_amount=net_total,
        currency_code=project_currency,
        status=CommitmentStatus.OPEN,
        committed_at=purchase_order.issued_at,
        revision=1,
    )
    db.add(commitment)
    await db.flush()

    for line in lines:
        requisition_line = (
            requisition_lines.get(line.requisition_line_id)
            if line.requisition_line_id is not None
            else None
        )
        db.add(
            ProjectCommitmentAllocation(
                organization_id=organization_id,
                project_id=project_id,
                commitment_id=commitment.id,
                line_number=line.line_number,
                source_line_id=line.id,
                wbs_code_id=line.wbs_code_id,
                boq_item_id=requisition_line.boq_item_id if requisition_line is not None else None,
                material_id=line.material_id,
                description=line.description,
                quantity=line.quantity,
                unit_code=line.unit_code,
                committed_amount=line.taxable_value,
                tax_amount=line.tax_amount,
                gross_amount=line.line_total,
            )
        )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.commitment.purchase_order.posted",
        target_type="project_commitment",
        target_id=str(commitment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "purchase_order_id": str(purchase_order.id),
            "purchase_order_number": purchase_order.number,
            "supplier_party_id": str(purchase_order.supplier_party_id),
            "committed_amount": net_total,
            "tax_snapshot": tax_total,
            "gross_snapshot": gross_total,
            "currency_code": project_currency,
            "amount_basis": "tax_exclusive_purchase_order_value",
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.commitment.posted",
        entity_type="project_commitment",
        entity_id=commitment.id,
        entity_version=commitment.revision,
        required_permission_key="financials.project_cost.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "source_type": CommitmentSourceType.PURCHASE_ORDER.value,
            "source_id": str(purchase_order.id),
            "source_number": purchase_order.number,
            "committed_amount": str(net_total),
            "tax_snapshot": str(tax_total),
            "gross_snapshot": str(gross_total),
            "currency_code": project_currency,
        },
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="project_commitment",
        entity_id=commitment.id,
        entity_version=commitment.revision,
    )
    return commitment
