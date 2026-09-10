from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.safety.models import InspectionRun, PunchItem, SafetyRecord
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def safety_record_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        record_id = UUID(entity_id)
    except ValueError:
        return None
    record = await db.scalar(
        select(SafetyRecord).where(
            SafetyRecord.id == record_id,
            SafetyRecord.organization_id == organization_id,
        )
    )
    if record is None:
        return None
    return SearchProjection(
        entity_type="safety_record",
        entity_id=str(record.id),
        entity_version=record.revision,
        required_permission_key="safety.record.view",
        scope_type="project",
        scope_id=str(record.project_id),
        title=record.title,
        subtitle=f"Safety {record.number} · {record.record_type.value} · {record.status.value}",
        body="\n".join(part for part in (record.description, record.location) if part),
        keywords=[record.record_type.value, record.severity.value, record.status.value],
        route_hint=f"/projects/{record.project_id}/safety/records/{record.id}",
        source_updated_at=record.updated_at,
    )


async def inspection_run_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        run_id = UUID(entity_id)
    except ValueError:
        return None
    run = await db.scalar(
        select(InspectionRun).where(
            InspectionRun.id == run_id,
            InspectionRun.organization_id == organization_id,
        )
    )
    if run is None:
        return None
    return SearchProjection(
        entity_type="inspection_run",
        entity_id=str(run.id),
        entity_version=run.revision,
        required_permission_key="safety.inspection.view",
        scope_type="project",
        scope_id=str(run.project_id),
        title=run.title,
        subtitle=f"Inspection {run.number} · {run.status.value}",
        body=run.location or "",
        keywords=["inspection", run.status.value],
        route_hint=f"/projects/{run.project_id}/inspections/{run.id}",
        source_updated_at=run.updated_at,
    )


async def punch_item_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        item_id = UUID(entity_id)
    except ValueError:
        return None
    item = await db.scalar(
        select(PunchItem).where(
            PunchItem.id == item_id,
            PunchItem.organization_id == organization_id,
        )
    )
    if item is None:
        return None
    return SearchProjection(
        entity_type="punch_item",
        entity_id=str(item.id),
        entity_version=item.revision,
        required_permission_key="safety.punch.view",
        scope_type="project",
        scope_id=str(item.project_id),
        title=item.title,
        subtitle=f"Punch {item.number} · {item.status.value}",
        body="\n".join(part for part in (item.description, item.location) if part),
        keywords=[item.priority.value, item.status.value, "punch"],
        route_hint=f"/projects/{item.project_id}/punch/{item.id}",
        source_updated_at=item.updated_at,
    )


for entity_type, provider in (
    ("safety_record", safety_record_search_projection),
    ("inspection_run", inspection_run_search_projection),
    ("punch_item", punch_item_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
