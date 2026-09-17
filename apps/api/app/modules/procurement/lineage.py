from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import BOQItem
from app.modules.procurement.models import PurchaseOrderLine, PurchaseRequisitionLine
from app.modules.procurement.service import (
    ProcurementValidationError,
    add_purchase_order_line as _add_purchase_order_line,
    add_requisition_line as _add_requisition_line,
)


def _inherit_reference(
    values: dict[str, object],
    *,
    key: str,
    authoritative_id: UUID | None,
    label: str,
    source: str,
) -> None:
    if authoritative_id is None:
        return
    supplied = values.get(key)
    if supplied is not None and supplied != authoritative_id:
        raise ProcurementValidationError(f"{label} must match {source}")
    values[key] = authoritative_id


def _apply_source_requisition_lineage(
    values: dict[str, object],
    *,
    material_id: UUID | None,
    wbs_code_id: UUID | None,
    boq_item_id: UUID | None,
) -> None:
    _inherit_reference(
        values,
        key="material_id",
        authoritative_id=material_id,
        label="Material",
        source="the source requisition line",
    )
    _inherit_reference(
        values,
        key="wbs_code_id",
        authoritative_id=wbs_code_id,
        label="WBS code",
        source="the source requisition line",
    )
    _inherit_reference(
        values,
        key="boq_item_id",
        authoritative_id=boq_item_id,
        label="BOQ item",
        source="the source requisition line",
    )


def _apply_boq_wbs_lineage(
    values: dict[str, object],
    *,
    wbs_code_id: UUID | None,
) -> None:
    _inherit_reference(
        values,
        key="wbs_code_id",
        authoritative_id=wbs_code_id,
        label="WBS code",
        source="the referenced BOQ item",
    )


async def _apply_boq_lineage(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: dict[str, object],
) -> None:
    boq_item_id = values.get("boq_item_id")
    if not isinstance(boq_item_id, UUID):
        return
    boq_item = await db.scalar(
        select(BOQItem).where(
            BOQItem.id == boq_item_id,
            BOQItem.project_id == project_id,
            BOQItem.organization_id == organization_id,
        )
    )
    if boq_item is None:
        raise ProcurementValidationError("BOQ item was not found in this project")
    _apply_boq_wbs_lineage(values, wbs_code_id=boq_item.wbs_code_id)


async def add_requisition_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    requisition_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseRequisitionLine:
    data = dict(values)
    await _apply_boq_lineage(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values=data,
    )
    return await _add_requisition_line(
        db,
        organization_id=organization_id,
        project_id=project_id,
        requisition_id=requisition_id,
        values=data,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def add_purchase_order_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    purchase_order_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> PurchaseOrderLine:
    data = dict(values)
    requisition_line_id = data.get("requisition_line_id")
    if isinstance(requisition_line_id, UUID):
        requisition_line = await db.scalar(
            select(PurchaseRequisitionLine).where(
                PurchaseRequisitionLine.id == requisition_line_id,
                PurchaseRequisitionLine.project_id == project_id,
                PurchaseRequisitionLine.organization_id == organization_id,
            )
        )
        if requisition_line is None:
            raise ProcurementValidationError("Requisition line was not found in this project")
        _apply_source_requisition_lineage(
            data,
            material_id=requisition_line.material_id,
            wbs_code_id=requisition_line.wbs_code_id,
            boq_item_id=requisition_line.boq_item_id,
        )

    await _apply_boq_lineage(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values=data,
    )
    return await _add_purchase_order_line(
        db,
        organization_id=organization_id,
        project_id=project_id,
        purchase_order_id=purchase_order_id,
        values=data,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
