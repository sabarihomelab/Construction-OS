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
)
from app.modules.search.service import schedule_search_index
from app.modules.subcontracts.models import Subcontract, SubcontractLine, SubcontractStatus


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _common_wbs_id(lines: list[object]) -> UUID | None:
    wbs_values = [getattr(line, "wbs_code_id") for line in lines]
    if wbs_values and all(value is not None for value in wbs_values):
        distinct_wbs = set(wbs_values)
        if len(distinct_wbs) == 1:
            return next(iter(distinct_wbs))
    return None


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

    commitment = ProjectCommitment(
        organization_id=organization_id,
        project_id=project_id,
        source_type=CommitmentSourceType.PURCHASE_ORDER,
        source_id=purchase_order.id,
        source_number=purchase_order.number,
        party_id=purchase_order.supplier_party_id,
        wbs_code_id=_common_wbs_id(lines),
        committed_amount=net_total,
        currency_code=project_currency,
        status=CommitmentStatus.OPEN,
        committed_at=purchase_order.issued_at,
        revision=1,
    )
    db.add(commitment)
    await db.flush()

    for line in lines:
        db.add(
            ProjectCommitmentAllocation(
                organization_id=organization_id,
                project_id=project_id,
                commitment_id=commitment.id,
                line_number=line.line_number,
                source_line_id=line.id,
                subcontract_line_id=None,
                wbs_code_id=line.wbs_code_id,
                boq_item_id=line.boq_item_id,
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


async def post_subcontract_commitment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subcontract_id: UUID,
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
            ProjectCommitment.source_type == CommitmentSourceType.SUBCONTRACT,
            ProjectCommitment.source_id == subcontract_id,
        )
    )
    if existing is not None:
        return existing

    subcontract = await db.scalar(
        select(Subcontract).where(
            Subcontract.id == subcontract_id,
            Subcontract.organization_id == organization_id,
            Subcontract.project_id == project_id,
        )
    )
    if subcontract is None:
        raise FinancialValidationError("Subcontract was not found in this project")
    if subcontract.status not in {
        SubcontractStatus.ISSUED,
        SubcontractStatus.ACTIVE,
        SubcontractStatus.COMPLETED,
    }:
        raise FinancialValidationError(
            "Only an issued subcontract can create a project commitment"
        )
    if subcontract.issued_at is None:
        raise FinancialValidationError(
            "Issued subcontract is missing its authoritative issued timestamp"
        )

    project_currency = (project.currency_code or "INR").upper()
    if subcontract.currency_code.upper() != project_currency:
        raise FinancialValidationError(
            "Subcontract currency must match project currency before commitment posting"
        )

    lines = list(
        (
            await db.scalars(
                select(SubcontractLine)
                .where(
                    SubcontractLine.organization_id == organization_id,
                    SubcontractLine.project_id == project_id,
                    SubcontractLine.subcontract_id == subcontract.id,
                )
                .order_by(SubcontractLine.line_number)
            )
        ).all()
    )
    if not lines:
        raise FinancialValidationError("Issued subcontract has no lines")
    if any(line.quantity <= 0 for line in lines):
        raise FinancialValidationError(
            "Subcontract commitment lines must have positive quantities"
        )

    committed_total = _money(sum((line.amount for line in lines), start=Decimal(0)))
    if committed_total != subcontract.original_amount:
        raise FinancialConflictError(
            "Subcontract header amount does not reconcile to its authoritative lines"
        )
    if committed_total <= 0:
        raise FinancialValidationError(
            "Subcontract must have a positive value before commitment posting"
        )

    commitment = ProjectCommitment(
        organization_id=organization_id,
        project_id=project_id,
        source_type=CommitmentSourceType.SUBCONTRACT,
        source_id=subcontract.id,
        source_number=subcontract.number,
        party_id=subcontract.contractor_party_id,
        wbs_code_id=_common_wbs_id(lines),
        committed_amount=committed_total,
        currency_code=project_currency,
        status=CommitmentStatus.OPEN,
        committed_at=subcontract.issued_at,
        revision=1,
    )
    db.add(commitment)
    await db.flush()

    for line in lines:
        db.add(
            ProjectCommitmentAllocation(
                organization_id=organization_id,
                project_id=project_id,
                commitment_id=commitment.id,
                line_number=line.line_number,
                source_line_id=None,
                subcontract_line_id=line.id,
                wbs_code_id=line.wbs_code_id,
                boq_item_id=line.boq_item_id,
                material_id=None,
                description=line.description,
                quantity=line.quantity,
                unit_code=line.unit_code,
                committed_amount=line.amount,
                tax_amount=Decimal(0),
                gross_amount=line.amount,
            )
        )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.commitment.subcontract.posted",
        target_type="project_commitment",
        target_id=str(commitment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "subcontract_id": str(subcontract.id),
            "subcontract_number": subcontract.number,
            "contractor_party_id": str(subcontract.contractor_party_id),
            "committed_amount": committed_total,
            "currency_code": project_currency,
            "amount_basis": "tax_exclusive_subcontract_line_value",
            "retention_percent": subcontract.retention_percent,
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
            "source_type": CommitmentSourceType.SUBCONTRACT.value,
            "source_id": str(subcontract.id),
            "source_number": subcontract.number,
            "committed_amount": str(committed_total),
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
