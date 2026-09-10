from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.meetings.models import (
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
    MeetingAttendee,
    MeetingHistoryEvent,
    MeetingReference,
    MeetingSeries,
)
from app.modules.meetings.schemas import (
    AgendaItemCreate,
    AgendaItemRead,
    MeetingActionCreate,
    MeetingActionRead,
    MeetingActionUpdate,
    MeetingAttendeeCreate,
    MeetingAttendeeRead,
    MeetingCreate,
    MeetingHistoryRead,
    MeetingMinutesUpdate,
    MeetingRead,
    MeetingReferenceCreate,
    MeetingReferenceRead,
    MeetingSeriesCreate,
    MeetingSeriesRead,
    MeetingSeriesUpdate,
    MeetingUpdate,
    MeetingVersionAction,
)
from app.modules.meetings.service import (
    MeetingConflictError,
    MeetingValidationError,
    add_action_item,
    add_agenda_item,
    add_attendee,
    add_reference,
    cancel_meeting,
    create_meeting,
    create_series,
    finalize_meeting,
    update_action_item,
    update_meeting,
    update_minutes,
    update_series,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["meetings"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, MeetingConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/projects/{project_id}/meeting-series", response_model=list[MeetingSeriesRead])
async def list_meeting_series(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeetingSeries]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.view")
    rows = await db.scalars(
        select(MeetingSeries)
        .where(
            MeetingSeries.organization_id == context.organization_id,
            MeetingSeries.project_id == project_id,
        )
        .order_by(MeetingSeries.name)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/meeting-series",
    response_model=MeetingSeriesRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting_series_route(
    project_id: UUID,
    payload: MeetingSeriesCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingSeries:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.series.manage")
    try:
        row = await create_series(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/meeting-series/{series_id}",
    response_model=MeetingSeriesRead,
)
async def update_meeting_series_route(
    project_id: UUID,
    series_id: UUID,
    payload: MeetingSeriesUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingSeries:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.series.manage")
    try:
        row = await update_series(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            series_id=series_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get("/projects/{project_id}/meetings", response_model=list[MeetingRead])
async def list_meetings(project_id: UUID, db: DbSession, session: CurrentSession) -> list[Meeting]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.view")
    rows = await db.scalars(
        select(Meeting)
        .where(Meeting.organization_id == context.organization_id, Meeting.project_id == project_id)
        .order_by(Meeting.start_at.desc(), Meeting.number.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/meetings",
    response_model=MeetingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting_route(
    project_id: UUID,
    payload: MeetingCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Meeting:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.create")
    try:
        row = await create_meeting(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            values=payload.model_dump(),
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/projects/{project_id}/meetings/{meeting_id}", response_model=MeetingRead)
async def update_meeting_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Meeting:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.update")
    try:
        row = await update_meeting(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            meeting_id=meeting_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.put("/projects/{project_id}/meetings/{meeting_id}/minutes", response_model=MeetingRead)
async def update_minutes_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingMinutesUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Meeting:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.minutes.manage")
    try:
        row = await update_minutes(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            meeting_id=meeting_id,
            expected_revision=payload.expected_revision,
            minutes=payload.minutes,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/meetings/{meeting_id}/finalize", response_model=MeetingRead)
async def finalize_meeting_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Meeting:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.minutes.finalize")
    try:
        row = await finalize_meeting(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            meeting_id=meeting_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.post("/projects/{project_id}/meetings/{meeting_id}/cancel", response_model=MeetingRead)
async def cancel_meeting_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingVersionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> Meeting:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.manage")
    try:
        row = await cancel_meeting(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            meeting_id=meeting_id,
            expected_revision=payload.expected_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/meetings/{meeting_id}/attendees",
    response_model=list[MeetingAttendeeRead],
)
async def list_attendees(
    project_id: UUID,
    meeting_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeetingAttendee]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.view")
    rows = await db.scalars(
        select(MeetingAttendee).where(
            MeetingAttendee.organization_id == context.organization_id,
            MeetingAttendee.project_id == project_id,
            MeetingAttendee.meeting_id == meeting_id,
        )
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/meetings/{meeting_id}/attendees",
    response_model=MeetingAttendeeRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_attendee_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingAttendeeCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingAttendee:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.attendee.manage")
    try:
        row = await add_attendee(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            meeting_id=meeting_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/meetings/{meeting_id}/agenda",
    response_model=list[AgendaItemRead],
)
async def list_agenda(
    project_id: UUID,
    meeting_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeetingAgendaItem]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.view")
    rows = await db.scalars(
        select(MeetingAgendaItem)
        .where(
            MeetingAgendaItem.organization_id == context.organization_id,
            MeetingAgendaItem.project_id == project_id,
            MeetingAgendaItem.meeting_id == meeting_id,
        )
        .order_by(MeetingAgendaItem.sequence)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/meetings/{meeting_id}/agenda",
    response_model=AgendaItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_agenda_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: AgendaItemCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingAgendaItem:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.agenda.manage")
    try:
        row = await add_agenda_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            meeting_id=meeting_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/meetings/{meeting_id}/actions",
    response_model=list[MeetingActionRead],
)
async def list_actions(
    project_id: UUID,
    meeting_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeetingActionItem]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.action.view")
    rows = await db.scalars(
        select(MeetingActionItem)
        .where(
            MeetingActionItem.organization_id == context.organization_id,
            MeetingActionItem.project_id == project_id,
            MeetingActionItem.meeting_id == meeting_id,
        )
        .order_by(MeetingActionItem.sequence)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/meetings/{meeting_id}/actions",
    response_model=MeetingActionRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_action_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingActionCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingActionItem:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.action.manage")
    try:
        row = await add_action_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            membership_id=context.membership_id,
            meeting_id=meeting_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/meetings/{meeting_id}/actions/{action_id}",
    response_model=MeetingActionRead,
)
async def update_action_route(
    project_id: UUID,
    meeting_id: UUID,
    action_id: UUID,
    payload: MeetingActionUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingActionItem:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.action.manage")
    try:
        row = await update_action_item(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            meeting_id=meeting_id,
            action_id=action_id,
            expected_revision=payload.expected_revision,
            changes=payload.model_dump(exclude={"expected_revision", "reason"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/meetings/{meeting_id}/references",
    response_model=list[MeetingReferenceRead],
)
async def list_references(
    project_id: UUID,
    meeting_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeetingReference]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.view")
    rows = await db.scalars(
        select(MeetingReference).where(
            MeetingReference.organization_id == context.organization_id,
            MeetingReference.project_id == project_id,
            MeetingReference.meeting_id == meeting_id,
        )
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/meetings/{meeting_id}/references",
    response_model=MeetingReferenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_reference_route(
    project_id: UUID,
    meeting_id: UUID,
    payload: MeetingReferenceCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MeetingReference:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.reference.manage")
    try:
        row = await add_reference(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            meeting_id=meeting_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (MeetingConflictError, MeetingValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.get(
    "/projects/{project_id}/meetings/{meeting_id}/history",
    response_model=list[MeetingHistoryRead],
)
async def list_history(
    project_id: UUID,
    meeting_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[MeetingHistoryEvent]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "meetings.meeting.view")
    rows = await db.scalars(
        select(MeetingHistoryEvent)
        .where(
            MeetingHistoryEvent.organization_id == context.organization_id,
            MeetingHistoryEvent.project_id == project_id,
            MeetingHistoryEvent.meeting_id == meeting_id,
        )
        .order_by(MeetingHistoryEvent.created_at, MeetingHistoryEvent.id)
    )
    return list(rows.all())
