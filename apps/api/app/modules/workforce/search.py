from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection
from app.modules.workforce.models import Timecard, Worker


async def worker_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        worker_id = UUID(entity_id)
    except ValueError:
        return None
    worker = await db.scalar(
        select(Worker).where(
            Worker.id == worker_id,
            Worker.organization_id == organization_id,
        )
    )
    if worker is None:
        return None
    name = " ".join(part for part in (worker.first_name, worker.last_name) if part)
    body = "\n".join(
        part
        for part in (
            worker.job_title,
            worker.trade,
            worker.classification,
            worker.email,
            worker.phone,
        )
        if part
    )
    return SearchProjection(
        entity_type="worker",
        entity_id=str(worker.id),
        entity_version=worker.revision,
        required_permission_key="workforce.worker.view",
        title=name,
        subtitle=worker.worker_number,
        body=body,
        keywords=[worker.worker_number, worker.status.value],
        route_hint=f"/workforce/workers/{worker.id}",
        source_updated_at=worker.updated_at,
    )


async def timecard_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        timecard_id = UUID(entity_id)
    except ValueError:
        return None
    timecard = await db.scalar(
        select(Timecard).where(
            Timecard.id == timecard_id,
            Timecard.organization_id == organization_id,
        )
    )
    if timecard is None:
        return None
    worker = await db.scalar(
        select(Worker).where(
            Worker.id == timecard.worker_id,
            Worker.organization_id == organization_id,
        )
    )
    worker_name = (
        f"{worker.first_name} {worker.last_name}" if worker is not None else str(timecard.worker_id)
    )
    return SearchProjection(
        entity_type="timecard",
        entity_id=str(timecard.id),
        entity_version=timecard.revision,
        required_permission_key="workforce.timecard.view",
        scope_type="project",
        scope_id=str(timecard.project_id),
        title=f"{worker_name} · {timecard.week_start.isoformat()}",
        subtitle=timecard.status.value,
        body="",
        keywords=[worker_name, timecard.week_start.isoformat(), timecard.status.value],
        route_hint=f"/projects/{timecard.project_id}/timecards/{timecard.id}",
        source_updated_at=timecard.updated_at,
    )


if not search_projection_providers.contains("worker"):
    search_projection_providers.register("worker", worker_search_projection)
if not search_projection_providers.contains("timecard"):
    search_projection_providers.register("timecard", timecard_search_projection)
