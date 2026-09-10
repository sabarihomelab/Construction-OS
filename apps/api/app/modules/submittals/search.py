from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection
from app.modules.submittals.models import Submittal


async def submittal_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        submittal_id = UUID(entity_id)
    except ValueError:
        return None

    submittal = await db.scalar(
        select(Submittal).where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
    )
    if submittal is None:
        return None

    keywords = [
        f"Submittal {submittal.number}",
        submittal.title,
        submittal.status.value,
    ]
    if submittal.submittal_type:
        keywords.append(submittal.submittal_type)
    if submittal.latest_decision:
        keywords.append(submittal.latest_decision.value)

    body_parts = [submittal.description or ""]
    if submittal.required_on_site_date is not None:
        body_parts.append(f"Required on site {submittal.required_on_site_date.isoformat()}")

    return SearchProjection(
        entity_type="submittal",
        entity_id=str(submittal.id),
        entity_version=submittal.version,
        required_permission_key="submittals.submittal.view",
        scope_type="project",
        scope_id=str(submittal.project_id),
        title=submittal.title,
        subtitle=f"Submittal {submittal.number} · {submittal.status.value}",
        body="\n".join(body_parts),
        keywords=keywords,
        route_hint=f"/projects/{submittal.project_id}/submittals/{submittal.id}",
        source_updated_at=submittal.updated_at,
    )


if not search_projection_providers.contains("submittal"):
    search_projection_providers.register("submittal", submittal_search_projection)
