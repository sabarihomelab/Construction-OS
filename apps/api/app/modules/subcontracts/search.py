from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection
from app.modules.subcontracts.models import Subcontract, SubcontractClaim


async def subcontract_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(Subcontract).where(
            Subcontract.id == row_id,
            Subcontract.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="subcontract",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="subcontracts.contract.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.title,
        subtitle=row.number,
        body=row.description or row.notes or "",
        keywords=[row.number, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/subcontracts/{row.id}",
        source_updated_at=row.updated_at,
    )


async def subcontract_claim_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(SubcontractClaim).where(
            SubcontractClaim.id == row_id,
            SubcontractClaim.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="subcontract_claim",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="subcontracts.claim.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=f"Progress Claim {row.number}",
        subtitle=row.status.value,
        body=row.notes or "",
        keywords=[row.number, row.status.value, str(row.gross_amount), str(row.certified_amount)],
        route_hint=f"/projects/{row.project_id}/subcontract-claims/{row.id}",
        source_updated_at=row.updated_at,
    )


for entity_type, provider in (
    ("subcontract", subcontract_search_projection),
    ("subcontract_claim", subcontract_claim_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
