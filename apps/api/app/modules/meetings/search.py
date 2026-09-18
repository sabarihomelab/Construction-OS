from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.models import Meeting, MeetingActionItem
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def meeting_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        meeting_id = UUID(entity_id)
    except ValueError:
        return None
    meeting = await db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.organization_id == organization_id,
        )
    )
    if meeting is None:
        return None
    return SearchProjection(
        entity_type="meeting",
        entity_id=str(meeting.id),
        entity_version=meeting.revision,
        required_permission_key="meetings.meeting.view",
        scope_type="project",
        scope_id=str(meeting.project_id),
        title=meeting.title,
        subtitle=f"Meeting #{meeting.number} · {meeting.status.value}",
        body="\n".join(value for value in (meeting.category, meeting.location, meeting.minutes) if value),
        keywords=[str(meeting.number), meeting.status.value, meeting.category or ""],
        route_hint=f"/projects/{meeting.project_id}/meetings/{meeting.id}",
        source_updated_at=meeting.updated_at,
    )


async def meeting_action_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        action_id = UUID(entity_id)
    except ValueError:
        return None
    action = await db.scalar(
        select(MeetingActionItem).where(
            MeetingActionItem.id == action_id,
            MeetingActionItem.organization_id == organization_id,
        )
    )
    if action is None:
        return None
    return SearchProjection(
        entity_type="meeting_action_item",
        entity_id=str(action.id),
        entity_version=action.revision,
        required_permission_key="meetings.action.view",
        scope_type="project",
        scope_id=str(action.project_id),
        title=action.description[:255],
        subtitle=action.status.value,
        body="",
        keywords=[action.status.value, str(action.sequence)],
        route_hint=f"/projects/{action.project_id}/meetings/{action.meeting_id}",
        source_updated_at=action.updated_at,
    )


if not search_projection_providers.contains("meeting"):
    search_projection_providers.register("meeting", meeting_search_projection)
if not search_projection_providers.contains("meeting_action_item"):
    search_projection_providers.register("meeting_action_item", meeting_action_search_projection)
