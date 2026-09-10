from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbSession
from app.modules.events.schemas import RealtimeEventBatch, RealtimeEventRead
from app.modules.events.service import list_visible_events_after
from app.modules.features.service import build_access_context
from app.modules.sessions.deps import CurrentSession

router = APIRouter(prefix="/realtime", tags=["realtime"])


@router.get("/events", response_model=RealtimeEventBatch)
async def get_realtime_events(
    db: DbSession,
    session: CurrentSession,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> RealtimeEventBatch:
    context = await build_access_context(db, session.membership_id)
    page = await list_visible_events_after(
        db,
        organization_id=UUID(context.organization_id),
        after_sequence=after,
        permission_keys=set(context.permissions),
        membership_id=session.membership_id,
        limit=limit,
    )
    return RealtimeEventBatch(
        next_cursor=page.next_cursor,
        events=[RealtimeEventRead.model_validate(event) for event in page.events],
    )
