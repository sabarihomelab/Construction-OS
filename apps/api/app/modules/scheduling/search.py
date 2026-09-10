from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduling.models import ProjectSchedule, ScheduleActivity
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def schedule_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(ProjectSchedule).where(
            ProjectSchedule.id == row_id,
            ProjectSchedule.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="project_schedule",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="scheduling.schedule.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.name,
        subtitle=f"Schedule {row.code}",
        body=row.description or row.notes or "",
        keywords=[row.code, row.status.value],
        route_hint=f"/projects/{row.project_id}/scheduling/schedules/{row.id}",
        source_updated_at=row.updated_at,
    )


async def activity_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(ScheduleActivity).where(
            ScheduleActivity.id == row_id,
            ScheduleActivity.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="schedule_activity",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="scheduling.schedule.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.name,
        subtitle=f"Activity {row.activity_code}",
        body=row.description or row.notes or "",
        keywords=[row.activity_code, row.status.value, str(row.percent_complete)],
        route_hint=f"/projects/{row.project_id}/scheduling/schedules/{row.schedule_id}",
        source_updated_at=row.updated_at,
    )


for entity_type, provider in (
    ("project_schedule", schedule_search_projection),
    ("schedule_activity", activity_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
