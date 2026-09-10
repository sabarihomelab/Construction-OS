from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.procurement.models import ProcurementProjectCounter


async def allocate_procurement_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    kind: str,
) -> int:
    columns = {
        "requisition": ProcurementProjectCounter.next_requisition_number,
        "po": ProcurementProjectCounter.next_po_number,
        "grn": ProcurementProjectCounter.next_grn_number,
    }
    column = columns.get(kind)
    if column is None:
        raise ValueError(f"Unknown procurement counter kind: {kind}")

    values = {
        "project_id": project_id,
        "organization_id": organization_id,
        "next_requisition_number": 1,
        "next_po_number": 1,
        "next_grn_number": 1,
    }
    values[column.key] = 2
    statement = (
        insert(ProcurementProjectCounter)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[ProcurementProjectCounter.project_id],
            set_={column.key: column + 1},
            where=ProcurementProjectCounter.organization_id == organization_id,
        )
        .returning(column)
    )
    next_number = await db.scalar(statement)
    if next_number is None:
        raise ValueError("Procurement counter does not belong to this organization")
    return next_number - 1
