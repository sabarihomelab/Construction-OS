from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subcontracts.models import SubcontractProjectCounter


async def allocate_subcontract_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    kind: str,
) -> int:
    columns = {
        "contract": SubcontractProjectCounter.next_contract_number,
        "claim": SubcontractProjectCounter.next_claim_number,
    }
    column = columns.get(kind)
    if column is None:
        raise ValueError(f"Unknown subcontract counter kind: {kind}")
    values = {
        "project_id": project_id,
        "organization_id": organization_id,
        "next_contract_number": 1,
        "next_claim_number": 1,
    }
    values[column.key] = 2
    statement = (
        insert(SubcontractProjectCounter)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[SubcontractProjectCounter.project_id],
            set_={column.key: column + 1},
            where=SubcontractProjectCounter.organization_id == organization_id,
        )
        .returning(column)
    )
    next_number = await db.scalar(statement)
    if next_number is None:
        raise ValueError("Subcontract counter does not belong to this organization")
    return next_number - 1
