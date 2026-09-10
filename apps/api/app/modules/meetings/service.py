from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.documents.models import Document
from app.modules.drawings.models import DrawingSheet
from app.modules.events.service import enqueue_event
from app.modules.meetings.models import (
    Meeting,
    MeetingActionItem,
    MeetingActionStatus,
    MeetingAgendaItem,
    MeetingAttendee,
    MeetingHistoryEvent,
    MeetingHistoryType,
    MeetingProjectCounter,
    MeetingReference,
    MeetingReferenceType,
    MeetingSeries,
    MeetingStatus,
)
from app.modules.notifications.models import NotificationCategory
from app.modules.notifications.service import create_notification
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.rfis.models import RFI
from app.modules.search.service import schedule_search_index
from app.modules.submittals.models import Submittal
from app.modules.workflows.service import WorkflowValidationError, start_workflow_instance


class MeetingValidationError(ValueError):
    pass


class MeetingConflictError(MeetingValidationError):
    pass


def _setting(config, key: str, default: object) -> object:
    for setting in config.settings:
        if setting.key == key:
            return setting.value
    return default


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    found = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if found is None:
        raise MeetingValidationError("Project was not found")


async def _require_project_member(
    db: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    found = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if found is None:
        raise MeetingValidationError("Active project membership was not found")


async def _allocate_number(db: AsyncSession, organization_id: UUID, project_id: UUID) -> int:
    statement = (
        insert(MeetingProjectCounter)
        .values(organization_id=organization_id, project_id=project_id, next_number=2)
        .on_conflict_do_update(
            index_elements=[MeetingProjectCounter.organization_id, MeetingProjectCounter.project_id],
            set_={"next_number": MeetingProjectCounter.next_number + 1},
        )
        .returning(MeetingProjectCounter.next_number)
    )
    next_number = await db.scalar(statement)
    if next_number is None:
        raise MeetingValidationError("Unable to allocate meeting number")
    return next_number - 1


async def _load_meeting(
    db: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    *,
    expected_revision: int | None = None,
    lock: bool = False,
) -> Meeting:
    statement = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == organization_id,
        Meeting.project_id == project_id,
    )
    if lock:
        statement = statement.with_for_update()
    meeting = await db.scalar(statement)
    if meeting is None:
        raise MeetingValidationError("Meeting was not found")
    if expected_revision is not None and meeting.revision != expected_revision:
        raise MeetingConflictError(
            f"Meeting changed from revision {expected_revision} to {meeting.revision}; refresh before saving"
        )
    return meeting


async def _history(
    db: AsyncSession,
    meeting: Meeting,
    event_type: MeetingHistoryType,
    actor_user_id: UUID | None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        MeetingHistoryEvent(
            organization_id=meeting.organization_id,
            project_id=meeting.project_id,
            meeting_id=meeting.id,
            event_type=event_type,
            meeting_revision=meeting.revision,
            actor_user_id=actor_user_id,
            details=details or {},
        )
    )


async def _publish(
    db: AsyncSession,
    meeting: Meeting,
    event_type: str,
    actor_user_id: UUID | None,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=meeting.organization_id,
        event_type=event_type,
        entity_type="meeting",
        entity_id=meeting.id,
        entity_version=meeting.revision,
        required_permission_key="meetings.meeting.view",
        scope_type="project",
        scope_id=meeting.project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"number": meeting.number, "status": meeting.status.value, "revision": meeting.revision},
    )
    await schedule_search_index(
        db,
        organization_id=meeting.organization_id,
        entity_type="meeting",
        entity_id=meeting.id,
        entity_version=meeting.revision,
    )


async def create_series(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> MeetingSeries:
    await _require_project(db, organization_id, project_id)
    name = str(values.get("name", "")).strip()
    if not name:
        raise MeetingValidationError("Series name is required")
    duplicate = await db.scalar(
        select(MeetingSeries.id).where(
            MeetingSeries.organization_id == organization_id,
            MeetingSeries.project_id == project_id,
            MeetingSeries.name == name,
        )
    )
    if duplicate is not None:
        raise MeetingConflictError("A meeting series with this name already exists")
    payload = dict(values)
    payload["name"] = name
    series = MeetingSeries(organization_id=organization_id, project_id=project_id, **payload)
    db.add(series)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.series.created",
        target_type="meeting_series",
        target_id=str(series.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "name": name},
    )
    return series


async def update_series(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    series_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MeetingSeries:
    series = await db.scalar(
        select(MeetingSeries)
        .where(
            MeetingSeries.id == series_id,
            MeetingSeries.organization_id == organization_id,
            MeetingSeries.project_id == project_id,
        )
        .with_for_update()
    )
    if series is None:
        raise MeetingValidationError("Meeting series was not found")
    if series.revision != expected_revision:
        raise MeetingConflictError("Meeting series was changed by another user")
    allowed = {"name", "category", "default_location", "recurrence_rule", "active"}
    filtered = {key: value for key, value in changes.items() if key in allowed}
    if "name" in filtered:
        name = str(filtered["name"] or "").strip()
        if not name:
            raise MeetingValidationError("Series name is required")
        duplicate = await db.scalar(
            select(MeetingSeries.id).where(
                MeetingSeries.organization_id == organization_id,
                MeetingSeries.project_id == project_id,
                MeetingSeries.name == name,
                MeetingSeries.id != series.id,
            )
        )
        if duplicate is not None:
            raise MeetingConflictError("A meeting series with this name already exists")
        filtered["name"] = name
    for key, value in filtered.items():
        setattr(series, key, value)
    series.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.series.updated",
        target_type="meeting_series",
        target_id=str(series.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"after": filtered, "revision": series.revision},
    )
    return series


async def create_meeting(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> Meeting:
    await _require_project(db, organization_id, project_id)
    await _require_project_member(db, organization_id, project_id, membership_id)
    title = str(values.get("title", "")).strip()
    if not title:
        raise MeetingValidationError("Meeting title is required")
    series_id = values.get("series_id")
    if isinstance(series_id, UUID):
        series = await db.scalar(
            select(MeetingSeries).where(
                MeetingSeries.id == series_id,
                MeetingSeries.organization_id == organization_id,
                MeetingSeries.project_id == project_id,
                MeetingSeries.active.is_(True),
            )
        )
        if series is None:
            raise MeetingValidationError("Active meeting series was not found in this project")
    start_at = values.get("start_at")
    end_at = values.get("end_at")
    if isinstance(start_at, datetime) and isinstance(end_at, datetime) and end_at < start_at:
        raise MeetingValidationError("Meeting end cannot be before its start")
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="meetings",
        project_id=project_id,
    )
    payload = dict(values)
    payload["title"] = title
    meeting = Meeting(
        organization_id=organization_id,
        project_id=project_id,
        number=await _allocate_number(db, organization_id, project_id),
        organizer_membership_id=membership_id,
        configuration_context={
            "configuration_revisions": config.configuration_revisions,
            "project_template_version_id": (
                str(config.project_template_version_id) if config.project_template_version_id else None
            ),
        },
        **payload,
    )
    db.add(meeting)
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.CREATED, actor_user_id)
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.created",
        target_type="meeting",
        target_id=str(meeting.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "number": meeting.number},
    )
    await _publish(db, meeting, "meeting.created", actor_user_id, session_id)
    return meeting


async def update_meeting(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Meeting:
    meeting = await _load_meeting(
        db,
        organization_id,
        project_id,
        meeting_id,
        expected_revision=expected_revision,
        lock=True,
    )
    if meeting.status in {MeetingStatus.COMPLETED, MeetingStatus.CANCELLED}:
        raise MeetingValidationError("Completed or cancelled meetings cannot be edited")
    allowed = {"title", "category", "start_at", "end_at", "location", "status"}
    filtered = {key: value for key, value in changes.items() if key in allowed}
    if "title" in filtered:
        title = str(filtered["title"] or "").strip()
        if not title:
            raise MeetingValidationError("Meeting title is required")
        filtered["title"] = title
    next_start = filtered.get("start_at", meeting.start_at)
    next_end = filtered.get("end_at", meeting.end_at)
    if isinstance(next_start, datetime) and isinstance(next_end, datetime) and next_end < next_start:
        raise MeetingValidationError("Meeting end cannot be before its start")
    for key, value in filtered.items():
        setattr(meeting, key, value)
    meeting.revision += 1
    await db.flush()
    await _history(
        db,
        meeting,
        MeetingHistoryType.STARTED if meeting.status == MeetingStatus.IN_PROGRESS else MeetingHistoryType.UPDATED,
        actor_user_id,
        {"reason": reason, "fields": sorted(filtered)},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.updated",
        target_type="meeting",
        target_id=str(meeting.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"after": filtered, "revision": meeting.revision},
    )
    await _publish(db, meeting, "meeting.updated", actor_user_id, session_id)
    return meeting


async def update_minutes(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    expected_revision: int,
    minutes: str,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Meeting:
    meeting = await _load_meeting(
        db,
        organization_id,
        project_id,
        meeting_id,
        expected_revision=expected_revision,
        lock=True,
    )
    if meeting.status == MeetingStatus.CANCELLED:
        raise MeetingValidationError("Cancelled meeting minutes cannot be edited")
    if meeting.finalized_at is not None:
        raise MeetingValidationError("Finalized meeting minutes are immutable")
    meeting.minutes = minutes.strip()
    meeting.revision += 1
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.MINUTES_UPDATED, actor_user_id, {"reason": reason})
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.minutes.updated",
        target_type="meeting",
        target_id=str(meeting.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"revision": meeting.revision},
    )
    await _publish(db, meeting, "meeting.minutes.updated", actor_user_id, session_id)
    return meeting


async def finalize_meeting(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    meeting_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Meeting:
    meeting = await _load_meeting(
        db,
        organization_id,
        project_id,
        meeting_id,
        expected_revision=expected_revision,
        lock=True,
    )
    if meeting.status == MeetingStatus.CANCELLED:
        raise MeetingValidationError("Cancelled meetings cannot be finalized")
    if meeting.finalized_at is not None:
        return meeting
    if not (meeting.minutes or "").strip():
        raise MeetingValidationError("Minutes are required before finalization")
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="meetings",
        project_id=project_id,
    )
    approval_required = bool(_setting(config, "meetings.minutes.approval.required", False))
    meeting.configuration_context = {
        **meeting.configuration_context,
        "finalization_configuration_revisions": config.configuration_revisions,
        "minutes_approval_required": approval_required,
        "finalized_under_configuration_at": datetime.now(UTC).isoformat(),
    }
    if approval_required:
        definition_key = str(_setting(config, "meetings.minutes.workflow.definition_key", "")).strip()
        if not definition_key:
            raise MeetingValidationError("Meeting minutes approval is enabled but no workflow is configured")
        try:
            workflow = await start_workflow_instance(
                db,
                organization_id=organization_id,
                definition_key=definition_key,
                entity_type="meeting",
                entity_id=meeting.id,
                actor_user_id=actor_user_id,
            )
        except WorkflowValidationError as exc:
            raise MeetingValidationError(str(exc)) from exc
        meeting.workflow_instance_id = workflow.id
        meeting.status = MeetingStatus.IN_PROGRESS
    else:
        meeting.status = MeetingStatus.COMPLETED
        meeting.finalized_at = datetime.now(UTC)
    meeting.revision += 1
    await db.flush()
    await _history(
        db,
        meeting,
        MeetingHistoryType.FINALIZED,
        actor_user_id,
        {"approval_required": approval_required, "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.finalized",
        target_type="meeting",
        target_id=str(meeting.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"approval_required": approval_required, "revision": meeting.revision},
    )
    await _publish(db, meeting, "meeting.finalized", actor_user_id, session_id)
    return meeting


async def cancel_meeting(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Meeting:
    meeting = await _load_meeting(
        db,
        organization_id,
        project_id,
        meeting_id,
        expected_revision=expected_revision,
        lock=True,
    )
    if meeting.finalized_at is not None:
        raise MeetingValidationError("Finalized meetings cannot be cancelled")
    meeting.status = MeetingStatus.CANCELLED
    meeting.revision += 1
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.CANCELLED, actor_user_id, {"reason": reason})
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.cancelled",
        target_type="meeting",
        target_id=str(meeting.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"revision": meeting.revision},
    )
    await _publish(db, meeting, "meeting.cancelled", actor_user_id, session_id)
    return meeting


async def add_attendee(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    meeting_id: UUID,
    values: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MeetingAttendee:
    meeting = await _load_meeting(db, organization_id, project_id, meeting_id, lock=True)
    if meeting.finalized_at is not None:
        raise MeetingValidationError("Finalized meeting attendees cannot be changed")
    internal_id = values.get("membership_id")
    if isinstance(internal_id, UUID):
        await _require_project_member(db, organization_id, project_id, internal_id)
    else:
        config = await resolve_effective_configuration(
            db,
            organization_id=organization_id,
            membership_id=membership_id,
            module_key="meetings",
            project_id=project_id,
        )
        if not bool(_setting(config, "meetings.external_attendees.enabled", True)):
            raise MeetingValidationError("External attendees are disabled by project configuration")
        if not str(values.get("external_name") or "").strip():
            raise MeetingValidationError("External attendee name is required")
    attendee = MeetingAttendee(
        organization_id=organization_id,
        project_id=project_id,
        meeting_id=meeting.id,
        **values,
    )
    db.add(attendee)
    meeting.revision += 1
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.ATTENDEE_CHANGED, actor_user_id, {"attendee_id": str(attendee.id)})
    if attendee.membership_id is not None:
        await create_notification(
            db,
            organization_id=organization_id,
            recipient_membership_id=attendee.membership_id,
            event_type="meeting.invited",
            category=NotificationCategory.ASSIGNED,
            reason_code="meeting_invitation",
            reason_text="You were added to a project meeting.",
            title=meeting.title,
            message=f"Meeting #{meeting.number} is scheduled for {meeting.start_at.isoformat()}.",
            required_permission_key="meetings.meeting.view",
            scope_type="project",
            scope_id=project_id,
            entity_type="meeting",
            entity_id=meeting.id,
            dedupe_key=f"meeting:{meeting.id}:attendee:{attendee.membership_id}",
            created_by_user_id=actor_user_id,
        )
    await _publish(db, meeting, "meeting.attendee.changed", actor_user_id, session_id)
    return attendee


async def add_agenda_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    values: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MeetingAgendaItem:
    meeting = await _load_meeting(db, organization_id, project_id, meeting_id, lock=True)
    owner_id = values.get("owner_membership_id")
    if isinstance(owner_id, UUID):
        await _require_project_member(db, organization_id, project_id, owner_id)
    maximum = await db.scalar(
        select(func.max(MeetingAgendaItem.sequence)).where(MeetingAgendaItem.meeting_id == meeting.id)
    )
    item = MeetingAgendaItem(
        organization_id=organization_id,
        project_id=project_id,
        meeting_id=meeting.id,
        sequence=(maximum or 0) + 1,
        **values,
    )
    db.add(item)
    meeting.revision += 1
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.AGENDA_CHANGED, actor_user_id, {"agenda_item_id": str(item.id)})
    await _publish(db, meeting, "meeting.agenda.changed", actor_user_id, session_id)
    return item


async def add_action_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    meeting_id: UUID,
    values: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MeetingActionItem:
    meeting = await _load_meeting(db, organization_id, project_id, meeting_id, lock=True)
    assignee_id = values.get("assignee_membership_id")
    if isinstance(assignee_id, UUID):
        await _require_project_member(db, organization_id, project_id, assignee_id)
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="meetings",
        project_id=project_id,
    )
    payload = dict(values)
    if payload.get("due_at") is None:
        default_days = int(_setting(config, "meetings.actions.default_due_days", 7))
        payload["due_at"] = datetime.now(UTC) + timedelta(days=default_days)
    maximum = await db.scalar(
        select(func.max(MeetingActionItem.sequence)).where(MeetingActionItem.meeting_id == meeting.id)
    )
    item = MeetingActionItem(
        organization_id=organization_id,
        project_id=project_id,
        meeting_id=meeting.id,
        sequence=(maximum or 0) + 1,
        **payload,
    )
    db.add(item)
    meeting.revision += 1
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.ACTION_CHANGED, actor_user_id, {"action_item_id": str(item.id)})
    if item.assignee_membership_id is not None:
        await create_notification(
            db,
            organization_id=organization_id,
            recipient_membership_id=item.assignee_membership_id,
            event_type="meeting.action.assigned",
            category=NotificationCategory.ACTION_REQUIRED,
            reason_code="meeting_action_assigned",
            reason_text="A meeting action item was assigned to you.",
            title=f"Action from {meeting.title}",
            message=item.description,
            required_permission_key="meetings.action.view",
            scope_type="project",
            scope_id=project_id,
            entity_type="meeting_action_item",
            entity_id=item.id,
            dedupe_key=f"meeting-action:{item.id}:assignee:{item.assignee_membership_id}",
            created_by_user_id=actor_user_id,
        )
    await _publish(db, meeting, "meeting.action.changed", actor_user_id, session_id)
    return item


async def update_action_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    action_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MeetingActionItem:
    meeting = await _load_meeting(db, organization_id, project_id, meeting_id, lock=True)
    item = await db.scalar(
        select(MeetingActionItem)
        .where(
            MeetingActionItem.id == action_id,
            MeetingActionItem.meeting_id == meeting.id,
            MeetingActionItem.organization_id == organization_id,
        )
        .with_for_update()
    )
    if item is None:
        raise MeetingValidationError("Meeting action item was not found")
    if item.revision != expected_revision:
        raise MeetingConflictError("Meeting action item was changed by another user")
    allowed = {"description", "assignee_membership_id", "due_at", "status"}
    filtered = {key: value for key, value in changes.items() if key in allowed}
    assignee_id = filtered.get("assignee_membership_id")
    if isinstance(assignee_id, UUID):
        await _require_project_member(db, organization_id, project_id, assignee_id)
    for key, value in filtered.items():
        setattr(item, key, value)
    if item.status == MeetingActionStatus.COMPLETED and item.completed_at is None:
        item.completed_at = datetime.now(UTC)
    elif item.status != MeetingActionStatus.COMPLETED:
        item.completed_at = None
    item.revision += 1
    meeting.revision += 1
    await db.flush()
    await _history(
        db,
        meeting,
        MeetingHistoryType.ACTION_CHANGED,
        actor_user_id,
        {"action_item_id": str(item.id), "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="meeting.action.updated",
        target_type="meeting_action_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"after": filtered, "revision": item.revision},
    )
    await _publish(db, meeting, "meeting.action.changed", actor_user_id, session_id)
    return item


async def add_reference(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    meeting_id: UUID,
    values: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MeetingReference:
    meeting = await _load_meeting(db, organization_id, project_id, meeting_id, lock=True)
    reference_type = values.get("reference_type")
    reference_id = str(values.get("reference_id") or "").strip()
    if not reference_id:
        raise MeetingValidationError("reference_id is required")
    if reference_type != MeetingReferenceType.OTHER:
        try:
            target_id = UUID(reference_id)
        except ValueError as exc:
            raise MeetingValidationError("Known meeting references require a UUID target") from exc
        model = {
            MeetingReferenceType.RFI: RFI,
            MeetingReferenceType.SUBMITTAL: Submittal,
            MeetingReferenceType.DOCUMENT: Document,
            MeetingReferenceType.DRAWING: DrawingSheet,
        }.get(reference_type)
        if model is None:
            raise MeetingValidationError("Unsupported meeting reference type")
        target = await db.scalar(
            select(model.id).where(
                model.id == target_id,
                model.organization_id == organization_id,
                model.project_id == project_id,
            )
        )
        if target is None:
            raise MeetingValidationError("Referenced record was not found in this project")
    payload = dict(values)
    payload["reference_id"] = reference_id
    reference = MeetingReference(
        organization_id=organization_id,
        project_id=project_id,
        meeting_id=meeting.id,
        **payload,
    )
    db.add(reference)
    meeting.revision += 1
    await db.flush()
    await _history(db, meeting, MeetingHistoryType.REFERENCE_CHANGED, actor_user_id, {"reference_id": str(reference.id)})
    await _publish(db, meeting, "meeting.reference.changed", actor_user_id, session_id)
    return reference
