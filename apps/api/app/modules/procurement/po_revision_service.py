from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.financials.models import ProjectCommitment
from app.modules.procurement.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)
from app.modules.procurement.po_revision_models import PurchaseOrderRevision
from app.modules.procurement.service import (
    ProcurementConflictError,
    ProcurementValidationError,
    _publish,
    add_purchase_order_line,
)


async def list_purchase_order_revisions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_id: UUID,
) -> list[PurchaseOrderRevision]:
    po = await db.scalar(
        select(PurchaseOrder.id).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.project_id == project_id,
        )
    )
    if po is None:
        raise ProcurementValidationError("Purchase order was not found")
    rows = await db.scalars(
        select(PurchaseOrderRevision)
        .where(
            PurchaseOrderRevision.purchase_order_id == purchase_order_id,
            PurchaseOrderRevision.organization_id == organization_id,
            PurchaseOrderRevision.project_id == project_id,
        )
        .order_by(PurchaseOrderRevision.version_number)
    )
    return list(rows.all())


async def start_purchase_order_amendment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_id: UUID,
    expected_revision: int,
    reason: str,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseOrder:
    po = await db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.project_id == project_id,
        )
        .with_for_update()
    )
    if po is None:
        raise ProcurementValidationError("Purchase order was not found")
    if po.revision != expected_revision:
        raise ProcurementConflictError("Purchase order changed; refresh before amending")
    if po.status != PurchaseOrderStatus.ISSUED:
        raise ProcurementValidationError("Only an issued purchase order can be amended")

    receipt_count = int(
        await db.scalar(
            select(func.count(GoodsReceipt.id)).where(
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.project_id == project_id,
                GoodsReceipt.purchase_order_id == purchase_order_id,
            )
        )
        or 0
    )
    if receipt_count:
        raise ProcurementValidationError(
            "Purchase order cannot be amended after a goods receipt exists; use a controlled downstream correction"
        )

    commitment_count = int(
        await db.scalar(
            select(func.count(ProjectCommitment.id)).where(
                ProjectCommitment.organization_id == organization_id,
                ProjectCommitment.project_id == project_id,
                ProjectCommitment.source_id == purchase_order_id,
            )
        )
        or 0
    )
    if commitment_count:
        raise ProcurementValidationError(
            "Purchase order cannot be amended after a commitment is posted; reverse or cancel the commitment first"
        )

    latest_revision = await db.scalar(
        select(PurchaseOrderRevision)
        .where(
            PurchaseOrderRevision.purchase_order_id == purchase_order_id,
            PurchaseOrderRevision.organization_id == organization_id,
            PurchaseOrderRevision.project_id == project_id,
        )
        .order_by(PurchaseOrderRevision.version_number.desc())
        .limit(1)
        .with_for_update()
    )
    if latest_revision is None:
        raise ProcurementConflictError(
            "Issued purchase order has no immutable issue snapshot; apply migration and reissue before amending"
        )

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ProcurementValidationError("Purchase order amendment reason is required")
    latest_revision.superseded_reason = normalized_reason

    amendment_lines = values.get("lines")
    if not isinstance(amendment_lines, list) or not amendment_lines:
        raise ProcurementValidationError("Purchase order amendment requires at least one line")

    before_revision = po.revision
    po.status = PurchaseOrderStatus.DRAFT
    po.approved_by_membership_id = None
    po.approved_at = None
    po.issued_at = None
    if "expected_delivery_date" in values:
        po.expected_delivery_date = values.get("expected_delivery_date")
    if "notes" in values:
        po.notes = values.get("notes") if isinstance(values.get("notes"), str) else None
    po.revision += 1

    await db.execute(
        delete(PurchaseOrderLine).where(
            PurchaseOrderLine.organization_id == organization_id,
            PurchaseOrderLine.project_id == project_id,
            PurchaseOrderLine.purchase_order_id == purchase_order_id,
        )
    )
    await db.flush()

    for line_values in amendment_lines:
        if not isinstance(line_values, Mapping):
            raise ProcurementValidationError("Purchase order amendment line is invalid")
        await add_purchase_order_line(
            db,
            organization_id=organization_id,
            project_id=project_id,
            purchase_order_id=purchase_order_id,
            values=line_values,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="procurement.purchase_order.amendment_started",
        target_type="purchase_order",
        target_id=str(po.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=normalized_reason,
        changes={
            "before_revision": before_revision,
            "after_revision": po.revision,
            "superseded_version": latest_revision.version_number,
            "status": po.status.value,
            "line_count": len(amendment_lines),
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="procurement.purchase_order.amendment_started",
        entity_type="purchase_order",
        entity_id=po.id,
        entity_version=po.revision,
        permission="procurement.purchase_order.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return po
