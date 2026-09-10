from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.documents.models import DocumentRevision, SpecificationSection
from app.modules.drawings.models import DrawingRevision
from app.modules.events.service import enqueue_event
from app.modules.identity.models import MembershipStatus, OrganizationMembership
from app.modules.notifications.service import create_notification
from app.modules.projects.models import Project
from app.modules.rfis.models import (
    RFI,
    RFIHistoryEvent,
    RFIHistoryType,
    RFIReference,
    RFIReferenceType,
    RFIResponse,
    RFIResponseStatus,
    RFIStatus,
)
from app.modules.rfis.numbering import allocate_rfi_number
from app.modules.search.service import schedule_search_index


class RFIValidationError(ValueError):
    pass


class RFIConflictError(ValueError):
    pass


async def _history(
    db: AsyncSession,
    *,
    rfi: RFI,
    event_type: RFIHistoryType,
    actor_user_id: UUID | None,
    summary: str,
) -> None:
    db.add(
        RFIHistoryEvent(
            organization_id=rfi.organization_id,
            rfi_id=rfi.id,
            event_type=event_type,
            entity_version=rfi.version,
            actor_user_id=actor_user_id,
            summary=summary[:500],
        )
    )
    await db.flush()


async def _publish_change(
    db: AsyncSession,
    *,
    rfi: RFI,
    event_type: str,
    actor_user_id: UUID | None,
    correlation_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=rfi.organization_id,
        event_type=event_type,
        entity_type="rfi",
        entity_id=rfi.id,
        entity_version=rfi.version,
        required_permission_key="rfis.rfi.view",
        scope_type="project",
        scope_id=rfi.project_id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        payload={"number": rfi.number, "status": rfi.status.value, "version": rfi.version},
    )
    await schedule_search_index(
        db,
        organization_id=rfi.organization_id,
        entity_type="rfi",
        entity_id=rfi.id,
        entity_version=rfi.version,
        correlation_id=correlation_id,
    )


async def create_rfi(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subject: str,
    question: str,
    actor_user_id: UUID,
    due_date: date | None = None,
    priority: str | None = None,
    ball_in_court_membership_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> RFI:
    project = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise RFIValidationError("Project was not found")
    normalized_subject = subject.strip()
    normalized_question = question.strip()
    if not normalized_subject or not normalized_question:
        raise RFIValidationError("RFI subject and question are required")
    if ball_in_court_membership_id is not None:
        membership = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.id == ball_in_court_membership_id,
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        )
        if membership is None:
            raise RFIValidationError("Ball-in-court membership is not active in this company")

    number = await allocate_rfi_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    rfi = RFI(
        organization_id=organization_id,
        project_id=project_id,
        number=number,
        subject=normalized_subject,
        question=normalized_question,
        due_date=due_date,
        priority=priority.strip() if priority else None,
        ball_in_court_membership_id=ball_in_court_membership_id,
        created_by_user_id=actor_user_id,
    )
    db.add(rfi)
    await db.flush()
    await _history(
        db,
        rfi=rfi,
        event_type=RFIHistoryType.CREATED,
        actor_user_id=actor_user_id,
        summary="RFI created",
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="rfi.created",
        target_type="rfi",
        target_id=str(rfi.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        risk=AuditRisk.MEDIUM,
        changes={"number": number, "project_id": str(project_id), "subject": normalized_subject},
    )
    await _publish_change(
        db,
        rfi=rfi,
        event_type="rfi.created",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return rfi


async def open_rfi(
    db: AsyncSession,
    *,
    organization_id: UUID,
    rfi_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> RFI:
    rfi = await db.scalar(
        select(RFI)
        .where(RFI.id == rfi_id, RFI.organization_id == organization_id)
        .with_for_update()
    )
    if rfi is None:
        raise RFIValidationError("RFI was not found")
    if rfi.version != expected_version:
        raise RFIConflictError("RFI changed; refresh before opening")
    if rfi.status != RFIStatus.DRAFT:
        raise RFIConflictError("Only draft RFIs can be opened")
    rfi.status = RFIStatus.OPEN
    rfi.opened_at = datetime.now(UTC)
    rfi.version += 1
    await db.flush()
    await _history(
        db,
        rfi=rfi,
        event_type=RFIHistoryType.OPENED,
        actor_user_id=actor_user_id,
        summary="RFI opened",
    )
    await _publish_change(
        db,
        rfi=rfi,
        event_type="rfi.opened",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    if rfi.ball_in_court_membership_id is not None:
        await create_notification(
            db,
            organization_id=organization_id,
            recipient_membership_id=rfi.ball_in_court_membership_id,
            category="action_required",
            title=f"RFI {rfi.number} requires your response",
            body=rfi.subject,
            reason_code="rfi.ball_in_court",
            reason_text="You are currently responsible for this RFI.",
            required_permission_key="rfis.rfi.respond",
            scope_type="project",
            scope_id=str(rfi.project_id),
            entity_type="rfi",
            entity_id=str(rfi.id),
            entity_version=rfi.version,
            dedupe_key=f"rfi:{rfi.id}:opened:v{rfi.version}",
        )
    return rfi


async def set_ball_in_court(
    db: AsyncSession,
    *,
    organization_id: UUID,
    rfi_id: UUID,
    expected_version: int,
    membership_id: UUID | None,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> RFI:
    rfi = await db.scalar(
        select(RFI)
        .where(RFI.id == rfi_id, RFI.organization_id == organization_id)
        .with_for_update()
    )
    if rfi is None:
        raise RFIValidationError("RFI was not found")
    if rfi.version != expected_version:
        raise RFIConflictError("RFI changed; refresh before changing responsibility")
    if membership_id is not None:
        membership = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.id == membership_id,
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        )
        if membership is None:
            raise RFIValidationError("Ball-in-court membership is not active in this company")
    if rfi.ball_in_court_membership_id == membership_id:
        return rfi
    rfi.ball_in_court_membership_id = membership_id
    rfi.version += 1
    await db.flush()
    await _history(
        db,
        rfi=rfi,
        event_type=RFIHistoryType.BALL_IN_COURT_CHANGED,
        actor_user_id=actor_user_id,
        summary="RFI responsibility changed",
    )
    await _publish_change(
        db,
        rfi=rfi,
        event_type="rfi.ball_in_court.changed",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return rfi


async def add_response(
    db: AsyncSession,
    *,
    organization_id: UUID,
    rfi_id: UUID,
    response_text: str,
    actor_user_id: UUID,
    official: bool = False,
    correlation_id: UUID | None = None,
) -> RFIResponse:
    rfi = await db.scalar(
        select(RFI)
        .where(RFI.id == rfi_id, RFI.organization_id == organization_id)
        .with_for_update()
    )
    if rfi is None:
        raise RFIValidationError("RFI was not found")
    if rfi.status not in {RFIStatus.OPEN, RFIStatus.ANSWERED}:
        raise RFIConflictError("Responses can only be added to open or answered RFIs")
    text = response_text.strip()
    if not text:
        raise RFIValidationError("RFI response text is required")

    current_sequence = await db.scalar(
        select(func.max(RFIResponse.sequence)).where(RFIResponse.rfi_id == rfi.id)
    )
    if official:
        previous_rows = await db.scalars(
            select(RFIResponse).where(
                RFIResponse.rfi_id == rfi.id,
                RFIResponse.status == RFIResponseStatus.OFFICIAL,
            )
        )
        for previous in previous_rows.all():
            previous.status = RFIResponseStatus.SUPERSEDED

    now = datetime.now(UTC)
    response = RFIResponse(
        organization_id=organization_id,
        rfi_id=rfi.id,
        sequence=(current_sequence or 0) + 1,
        response_text=text,
        status=RFIResponseStatus.OFFICIAL if official else RFIResponseStatus.PROPOSED,
        responded_by_user_id=actor_user_id,
        responded_at=now,
        official_at=now if official else None,
    )
    db.add(response)
    rfi.version += 1
    if official:
        rfi.status = RFIStatus.ANSWERED
        rfi.answered_at = now
        rfi.ball_in_court_membership_id = None
    await db.flush()
    await _history(
        db,
        rfi=rfi,
        event_type=(
            RFIHistoryType.OFFICIAL_RESPONSE_SET if official else RFIHistoryType.RESPONSE_ADDED
        ),
        actor_user_id=actor_user_id,
        summary="Official RFI response issued" if official else "RFI response added",
    )
    await _publish_change(
        db,
        rfi=rfi,
        event_type="rfi.answered" if official else "rfi.response.added",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return response


async def add_reference(
    db: AsyncSession,
    *,
    organization_id: UUID,
    rfi_id: UUID,
    reference_type: RFIReferenceType,
    reference_id: UUID | str,
    label: str | None = None,
) -> RFIReference:
    rfi = await db.scalar(
        select(RFI).where(RFI.id == rfi_id, RFI.organization_id == organization_id)
    )
    if rfi is None:
        raise RFIValidationError("RFI was not found")
    reference_key = str(reference_id)
    if reference_type == RFIReferenceType.DRAWING_REVISION:
        target = await db.scalar(
            select(DrawingRevision.id).where(
                DrawingRevision.id == UUID(reference_key),
                DrawingRevision.organization_id == organization_id,
            )
        )
        if target is None:
            raise RFIValidationError("Drawing revision reference was not found")
    elif reference_type == RFIReferenceType.SPECIFICATION_SECTION:
        target = await db.scalar(
            select(SpecificationSection.id).where(
                SpecificationSection.id == UUID(reference_key),
                SpecificationSection.organization_id == organization_id,
            )
        )
        if target is None:
            raise RFIValidationError("Specification section reference was not found")
    elif reference_type == RFIReferenceType.DOCUMENT_REVISION:
        target = await db.scalar(
            select(DocumentRevision.id).where(
                DocumentRevision.id == UUID(reference_key),
                DocumentRevision.organization_id == organization_id,
            )
        )
        if target is None:
            raise RFIValidationError("Document revision reference was not found")
    elif reference_type in {RFIReferenceType.SCHEDULE_ACTIVITY, RFIReferenceType.CHANGE_EVENT}:
        raise RFIValidationError("This reference type is not available until its module is installed")

    existing = await db.scalar(
        select(RFIReference).where(
            RFIReference.rfi_id == rfi.id,
            RFIReference.reference_type == reference_type,
            RFIReference.reference_id == reference_key,
        )
    )
    if existing is not None:
        return existing
    reference = RFIReference(
        organization_id=organization_id,
        rfi_id=rfi.id,
        reference_type=reference_type,
        reference_id=reference_key,
        label=label,
    )
    db.add(reference)
    rfi.version += 1
    await db.flush()
    return reference


async def close_rfi(
    db: AsyncSession,
    *,
    organization_id: UUID,
    rfi_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> RFI:
    rfi = await db.scalar(
        select(RFI)
        .where(RFI.id == rfi_id, RFI.organization_id == organization_id)
        .with_for_update()
    )
    if rfi is None:
        raise RFIValidationError("RFI was not found")
    if rfi.version != expected_version:
        raise RFIConflictError("RFI changed; refresh before closing")
    if rfi.status != RFIStatus.ANSWERED:
        raise RFIConflictError("Only answered RFIs can be closed")
    rfi.status = RFIStatus.CLOSED
    rfi.closed_at = datetime.now(UTC)
    rfi.version += 1
    await db.flush()
    await _history(
        db,
        rfi=rfi,
        event_type=RFIHistoryType.CLOSED,
        actor_user_id=actor_user_id,
        summary="RFI closed",
    )
    await _publish_change(
        db,
        rfi=rfi,
        event_type="rfi.closed",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return rfi
