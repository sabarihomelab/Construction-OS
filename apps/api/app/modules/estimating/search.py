from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.estimating.models import ProjectBudget, ProjectEstimate
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def estimate_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(ProjectEstimate).where(
            ProjectEstimate.id == row_id,
            ProjectEstimate.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="project_estimate",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="estimating.estimate.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.name,
        subtitle=f"Estimate {row.code}",
        body=row.description or "",
        keywords=[row.code, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/estimating/estimates/{row.id}",
        source_updated_at=row.updated_at,
    )


async def budget_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(ProjectBudget).where(
            ProjectBudget.id == row_id,
            ProjectBudget.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="project_budget",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="estimating.budget.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.name,
        subtitle=f"Budget {row.code}",
        body=row.notes or "",
        keywords=[row.code, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/estimating/budgets/{row.id}",
        source_updated_at=row.updated_at,
    )


for entity_type, provider in (
    ("project_estimate", estimate_search_projection),
    ("project_budget", budget_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
