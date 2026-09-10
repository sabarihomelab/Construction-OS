from collections.abc import Mapping
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.documents.models import Document, DocumentRevision, SpecificationSection
from app.modules.drawings.models import DrawingRevision, DrawingSet, DrawingSheet
from app.modules.events.service import enqueue_event
from app.modules.notifications.models import NotificationCategory
from app.modules.notifications.service import create_notification
from app.modules.projects.models import (
    Project,
    ProjectMembership,
    ProjectMembershipStatus,
)
from app.modules.rfis.models import RFI
from app.modules.search.service import schedule_search_index
from app.modules.submittals.models import (
    Submittal,
    SubmittalHistoryEvent,
    SubmittalHistoryType,
    SubmittalReference,
    SubmittalReferenceType,
    SubmittalReview,
    SubmittalReviewDecision,
    SubmittalRevision,
    SubmittalRevisionStatus,
    SubmittalStatus,
)
from app.modules.submittals.numbering import allocate_submittal_number


class SubmittalValidationError(ValueError):
    pass


class SubmittalConflictError(ValueError):
    pass


_TERMINAL_STATUSES = {SubmittalStatus.CLOSED, SubmittalStatus.VOID}
_DECISION_STATUS = {
    SubmittalReviewDecision.APPROVED: SubmittalStatus.APPROVED,
    SubmittalReviewDecision.APPROVED_AS_NOTED: SubmittalStatus.APPROVED_AS_NOTED,
    SubmittalReviewDecision.REVISE_RESUBMIT: SubmittalStatus.REVISE_RESUBMIT,
    SubmittalReviewDecision.REJECTED: SubmittalStatus.REJECTED,
}


def _reference_uuid(reference_id: UUID | str) -> UUID:
    try:
        return reference_id if isinstance(reference_id, UUID) else UUID(reference_id)
    except ValueError as exc:
        raise SubmittalValidationError("Reference id must be a UUID") from exc


async def _history(
    db: AsyncSession,
    *,
    submittal: Submittal,
    event_type: SubmittalHistoryType,
    actor_user_id: UUID | None,
    summary: str,
) -> None:
    db.add(
        SubmittalHistoryEvent(
            organization_id=submittal.organization_id,
            submittal_id=submittal.id,
            event_type=event_type,
            entity_version=submittal.version,
            actor_user_id=actor_user_id,
            summary=summary[:500],
        )
    )
    await db.flush()


async def _publish_change(
    db: AsyncSession,
    *,
    submittal: Submittal,
    event_type: str,
    actor_user_id: UUID | None,
    correlation_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=submittal.organization_id,
        event_type=event_type,
        entity_type="submittal",
        entity_id=submittal.id,
        entity_version=submittal.version,
        required_permission_key="submittals.submittal.view",
        scope_type="project",
        scope_id=submittal.project_id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        payload={
            "number": submittal.number,
            "status": submittal.status.value,
            "version": submittal.version,
        },
    )
    await schedule_search_index(
        db,
        organization_id=submittal.organization_id,
        entity_type="submittal",
        entity_id=submittal.id,
        entity_version=submittal.version,
        correlation_id=correlation_id,
    )


async def _require_active_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    organization_membership_id: UUID,
) -> ProjectMembership:
    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == organization_membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise SubmittalValidationError("Member must be active on this project")
    return membership


async def _notify_reviewer(
    db: AsyncSession,
    *,
    submittal: Submittal,
    revision: SubmittalRevision,
    reviewer_membership_id: UUID,
    actor_user_id: UUID | None,
    correlation_id: UUID | None,
) -> None:
    await create_notification(
        db,
        organization_id=submittal.organization_id,
        recipient_membership_id=reviewer_membership_id,
        event_type="submittal.review.required",
        category=NotificationCategory.ACTION_REQUIRED,
        reason_code="submittal.review.required",
        reason_text="A submittal revision is awaiting your review.",
        title=f"Submittal {submittal.number} requires review",
        message=f"{submittal.title} · Revision {revision.revision_label}",
        required_permission_key="submittals.submittal.review",
        scope_type="project",
        scope_id=submittal.project_id,
        entity_type="submittal",
        entity_id=submittal.id,
        dedupe_key=f"submittal:{submittal.id}:revision:{revision.sequence}:review",
        created_by_user_id=actor_user_id,
        correlation_id=correlation_id,
    )


async def create_submittal(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    title: str,
    actor_user_id: UUID,
    description: str | None = None,
    submittal_type: str | None = None,
    due_date: date | None = None,
    required_on_site_date: date | None = None,
    lead_time_days: int | None = None,
    ball_in_court_membership_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> Submittal:
    project = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise SubmittalValidationError("Project was not found")
    normalized_title = title.strip()
    if not normalized_title:
        raise SubmittalValidationError("Submittal title is required")
    if lead_time_days is not None and lead_time_days < 0:
        raise SubmittalValidationError("Lead time cannot be negative")
    if ball_in_court_membership_id is not None:
        await _require_active_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            organization_membership_id=ball_in_court_membership_id,
        )

    number = await allocate_submittal_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    submittal = Submittal(
        organization_id=organization_id,
        project_id=project_id,
        number=number,
        title=normalized_title,
        description=description.strip() if description else None,
        submittal_type=submittal_type.strip() if submittal_type else None,
        due_date=due_date,
        required_on_site_date=required_on_site_date,
        lead_time_days=lead_time_days,
        ball_in_court_membership_id=ball_in_court_membership_id,
        created_by_user_id=actor_user_id,
    )
    db.add(submittal)
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.CREATED,
        actor_user_id=actor_user_id,
        summary="Submittal created",
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="submittal.created",
        target_type="submittal",
        target_id=str(submittal.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        risk=AuditRisk.MEDIUM,
        changes={
            "number": number,
            "project_id": str(project_id),
            "title": normalized_title,
        },
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.created",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return submittal


async def update_submittal(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    expected_version: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> Submittal:
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.version != expected_version:
        raise SubmittalConflictError("Submittal changed; refresh before updating")
    if submittal.status in _TERMINAL_STATUSES or submittal.status == SubmittalStatus.IN_REVIEW:
        raise SubmittalConflictError("Submittal cannot be edited in its current state")

    allowed = {
        "title",
        "description",
        "submittal_type",
        "due_date",
        "required_on_site_date",
        "lead_time_days",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise SubmittalValidationError(
            f"Unsupported Submittal fields: {', '.join(sorted(unknown))}"
        )

    for key, value in changes.items():
        if key == "title":
            normalized = str(value or "").strip()
            if not normalized:
                raise SubmittalValidationError("Submittal title cannot be blank")
            submittal.title = normalized
        elif key in {"description", "submittal_type"}:
            setattr(submittal, key, str(value).strip() if value is not None else None)
        elif key in {"due_date", "required_on_site_date"}:
            if value is not None and not isinstance(value, date):
                raise SubmittalValidationError(f"{key} must be a date")
            setattr(submittal, key, value)
        elif key == "lead_time_days":
            if value is not None and (not isinstance(value, int) or value < 0):
                raise SubmittalValidationError("Lead time must be a non-negative integer")
            submittal.lead_time_days = value

    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.UPDATED,
        actor_user_id=actor_user_id,
        summary="Submittal details updated",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.updated",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return submittal


async def open_submittal(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> Submittal:
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.version != expected_version:
        raise SubmittalConflictError("Submittal changed; refresh before opening")
    if submittal.status != SubmittalStatus.DRAFT:
        raise SubmittalConflictError("Only draft Submittals can be opened")
    submittal.status = SubmittalStatus.OPEN
    submittal.opened_at = datetime.now(UTC)
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.OPENED,
        actor_user_id=actor_user_id,
        summary="Submittal opened",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.opened",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return submittal


async def add_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    revision_label: str,
    actor_user_id: UUID,
    description: str | None = None,
    correlation_id: UUID | None = None,
) -> SubmittalRevision:
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.status in _TERMINAL_STATUSES or submittal.status == SubmittalStatus.IN_REVIEW:
        raise SubmittalConflictError("A revision cannot be added in the current state")
    label = revision_label.strip()
    if not label:
        raise SubmittalValidationError("Submittal revision label is required")

    duplicate = await db.scalar(
        select(SubmittalRevision.id).where(
            SubmittalRevision.submittal_id == submittal.id,
            SubmittalRevision.revision_label == label,
        )
    )
    if duplicate is not None:
        raise SubmittalConflictError("Revision label already exists for this Submittal")
    current_draft = await db.scalar(
        select(SubmittalRevision.id).where(
            SubmittalRevision.submittal_id == submittal.id,
            SubmittalRevision.status == SubmittalRevisionStatus.DRAFT,
        )
    )
    if current_draft is not None:
        raise SubmittalConflictError("Finish or withdraw the current draft revision first")

    previous_rows = await db.scalars(
        select(SubmittalRevision).where(
            SubmittalRevision.submittal_id == submittal.id,
            SubmittalRevision.status == SubmittalRevisionStatus.REVIEWED,
        )
    )
    for previous in previous_rows.all():
        previous.status = SubmittalRevisionStatus.SUPERSEDED

    sequence = submittal.current_revision_sequence + 1
    revision = SubmittalRevision(
        organization_id=organization_id,
        submittal_id=submittal.id,
        sequence=sequence,
        revision_label=label,
        description=description.strip() if description else None,
    )
    db.add(revision)
    submittal.current_revision_sequence = sequence
    if submittal.status in {
        SubmittalStatus.REVISE_RESUBMIT,
        SubmittalStatus.REJECTED,
        SubmittalStatus.APPROVED,
        SubmittalStatus.APPROVED_AS_NOTED,
    }:
        submittal.status = SubmittalStatus.OPEN
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.REVISION_CREATED,
        actor_user_id=actor_user_id,
        summary=f"Revision {label} created",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.revision.created",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return revision


async def submit_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    revision_id: UUID,
    reviewer_membership_id: UUID,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> SubmittalRevision:
    revision = await db.scalar(
        select(SubmittalRevision)
        .where(
            SubmittalRevision.id == revision_id,
            SubmittalRevision.organization_id == organization_id,
        )
        .with_for_update()
    )
    if revision is None:
        raise SubmittalValidationError("Submittal revision was not found")
    if revision.status != SubmittalRevisionStatus.DRAFT:
        raise SubmittalConflictError("Only a draft revision can be submitted")
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == revision.submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.status in _TERMINAL_STATUSES:
        raise SubmittalConflictError("Closed or void Submittals cannot be submitted")
    await _require_active_project_membership(
        db,
        organization_id=organization_id,
        project_id=submittal.project_id,
        organization_membership_id=reviewer_membership_id,
    )

    now = datetime.now(UTC)
    revision.status = SubmittalRevisionStatus.IN_REVIEW
    revision.submitted_by_user_id = actor_user_id
    revision.submitted_at = now
    submittal.status = SubmittalStatus.IN_REVIEW
    submittal.ball_in_court_membership_id = reviewer_membership_id
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.REVISION_SUBMITTED,
        actor_user_id=actor_user_id,
        summary=f"Revision {revision.revision_label} submitted for review",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.revision.submitted",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    await _notify_reviewer(
        db,
        submittal=submittal,
        revision=revision,
        reviewer_membership_id=reviewer_membership_id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return revision


async def add_review(
    db: AsyncSession,
    *,
    organization_id: UUID,
    revision_id: UUID,
    reviewer_membership_id: UUID,
    decision: SubmittalReviewDecision,
    actor_user_id: UUID,
    comments: str | None = None,
    official: bool = False,
    correlation_id: UUID | None = None,
) -> SubmittalReview:
    revision = await db.scalar(
        select(SubmittalRevision)
        .where(
            SubmittalRevision.id == revision_id,
            SubmittalRevision.organization_id == organization_id,
        )
        .with_for_update()
    )
    if revision is None:
        raise SubmittalValidationError("Submittal revision was not found")
    if revision.status != SubmittalRevisionStatus.IN_REVIEW:
        raise SubmittalConflictError("Only an in-review revision can be reviewed")
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == revision.submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    await _require_active_project_membership(
        db,
        organization_id=organization_id,
        project_id=submittal.project_id,
        organization_membership_id=reviewer_membership_id,
    )
    if submittal.ball_in_court_membership_id != reviewer_membership_id:
        raise SubmittalConflictError("This Submittal is assigned to a different reviewer")
    if official and decision == SubmittalReviewDecision.COMMENT_ONLY:
        raise SubmittalValidationError("Comment-only reviews cannot be official decisions")
    if official:
        existing_official = await db.scalar(
            select(SubmittalReview.id).where(
                SubmittalReview.submittal_revision_id == revision.id,
                SubmittalReview.official.is_(True),
            )
        )
        if existing_official is not None:
            raise SubmittalConflictError("This revision already has an official decision")

    current_sequence = await db.scalar(
        select(func.max(SubmittalReview.sequence)).where(
            SubmittalReview.submittal_revision_id == revision.id
        )
    )
    review = SubmittalReview(
        organization_id=organization_id,
        project_id=submittal.project_id,
        submittal_revision_id=revision.id,
        sequence=(current_sequence or 0) + 1,
        reviewer_membership_id=reviewer_membership_id,
        decision=decision,
        comments=comments.strip() if comments else None,
        official=official,
        reviewed_at=datetime.now(UTC),
        reviewed_by_user_id=actor_user_id,
    )
    db.add(review)
    submittal.version += 1
    if official:
        revision.status = SubmittalRevisionStatus.REVIEWED
        submittal.latest_decision = decision
        submittal.status = _DECISION_STATUS[decision]
        submittal.ball_in_court_membership_id = None
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=(
            SubmittalHistoryType.DECISION_ISSUED
            if official
            else SubmittalHistoryType.REVIEW_ADDED
        ),
        actor_user_id=actor_user_id,
        summary=(
            f"Official decision issued: {decision.value}"
            if official
            else "Review comment added"
        ),
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.decision.issued" if official else "submittal.review.added",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return review


async def set_ball_in_court(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    expected_version: int,
    membership_id: UUID | None,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> Submittal:
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.version != expected_version:
        raise SubmittalConflictError("Submittal changed; refresh before changing responsibility")
    if submittal.status in _TERMINAL_STATUSES:
        raise SubmittalConflictError("Closed or void Submittals cannot change responsibility")
    if membership_id is not None:
        await _require_active_project_membership(
            db,
            organization_id=organization_id,
            project_id=submittal.project_id,
            organization_membership_id=membership_id,
        )
    if submittal.ball_in_court_membership_id == membership_id:
        return submittal
    submittal.ball_in_court_membership_id = membership_id
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.BALL_IN_COURT_CHANGED,
        actor_user_id=actor_user_id,
        summary="Submittal responsibility changed",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.ball_in_court.changed",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return submittal


async def add_reference(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    reference_type: SubmittalReferenceType,
    reference_id: UUID | str,
    actor_user_id: UUID,
    label: str | None = None,
    correlation_id: UUID | None = None,
) -> SubmittalReference:
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.status in _TERMINAL_STATUSES:
        raise SubmittalConflictError("References cannot be added to closed or void Submittals")
    reference_key = str(reference_id)

    if reference_type == SubmittalReferenceType.DRAWING_REVISION:
        target_id = _reference_uuid(reference_id)
        target = await db.scalar(
            select(DrawingRevision.id)
            .join(DrawingSheet, DrawingSheet.id == DrawingRevision.sheet_id)
            .join(DrawingSet, DrawingSet.id == DrawingSheet.drawing_set_id)
            .where(
                DrawingRevision.id == target_id,
                DrawingRevision.organization_id == organization_id,
                DrawingSheet.organization_id == organization_id,
                DrawingSet.organization_id == organization_id,
                DrawingSet.project_id == submittal.project_id,
            )
        )
        if target is None:
            raise SubmittalValidationError("Drawing revision was not found in this project")
    elif reference_type == SubmittalReferenceType.SPECIFICATION_SECTION:
        target_id = _reference_uuid(reference_id)
        target = await db.scalar(
            select(SpecificationSection.id)
            .join(Document, Document.id == SpecificationSection.document_id)
            .where(
                SpecificationSection.id == target_id,
                SpecificationSection.organization_id == organization_id,
                Document.organization_id == organization_id,
                Document.project_id == submittal.project_id,
            )
        )
        if target is None:
            raise SubmittalValidationError("Specification section was not found in this project")
    elif reference_type == SubmittalReferenceType.DOCUMENT_REVISION:
        target_id = _reference_uuid(reference_id)
        target = await db.scalar(
            select(DocumentRevision.id)
            .join(Document, Document.id == DocumentRevision.document_id)
            .where(
                DocumentRevision.id == target_id,
                DocumentRevision.organization_id == organization_id,
                Document.organization_id == organization_id,
                Document.project_id == submittal.project_id,
            )
        )
        if target is None:
            raise SubmittalValidationError("Document revision was not found in this project")
    elif reference_type == SubmittalReferenceType.RFI:
        target_id = _reference_uuid(reference_id)
        target = await db.scalar(
            select(RFI.id).where(
                RFI.id == target_id,
                RFI.organization_id == organization_id,
                RFI.project_id == submittal.project_id,
            )
        )
        if target is None:
            raise SubmittalValidationError("RFI was not found in this project")
    elif reference_type == SubmittalReferenceType.SCHEDULE_ACTIVITY:
        raise SubmittalValidationError(
            "Schedule activity references are unavailable until Scheduling is installed"
        )
    elif reference_type == SubmittalReferenceType.CUSTOM and not reference_key.strip():
        raise SubmittalValidationError("Custom Submittal reference id is required")

    existing = await db.scalar(
        select(SubmittalReference).where(
            SubmittalReference.submittal_id == submittal.id,
            SubmittalReference.reference_type == reference_type,
            SubmittalReference.reference_id == reference_key,
        )
    )
    if existing is not None:
        return existing
    reference = SubmittalReference(
        organization_id=organization_id,
        submittal_id=submittal.id,
        reference_type=reference_type,
        reference_id=reference_key,
        label=label,
    )
    db.add(reference)
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.UPDATED,
        actor_user_id=actor_user_id,
        summary=f"Reference added: {reference_type.value}",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.reference.added",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return reference


async def close_submittal(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    correlation_id: UUID | None = None,
) -> Submittal:
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.version != expected_version:
        raise SubmittalConflictError("Submittal changed; refresh before closing")
    if submittal.status not in {
        SubmittalStatus.APPROVED,
        SubmittalStatus.APPROVED_AS_NOTED,
    }:
        raise SubmittalConflictError("Only approved Submittals can be closed")
    submittal.status = SubmittalStatus.CLOSED
    submittal.closed_at = datetime.now(UTC)
    submittal.ball_in_court_membership_id = None
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.CLOSED,
        actor_user_id=actor_user_id,
        summary="Submittal closed",
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.closed",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return submittal


async def void_submittal(
    db: AsyncSession,
    *,
    organization_id: UUID,
    submittal_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    reason: str,
    correlation_id: UUID | None = None,
) -> Submittal:
    reason_text = reason.strip()
    if not reason_text:
        raise SubmittalValidationError("A reason is required to void a Submittal")
    submittal = await db.scalar(
        select(Submittal)
        .where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
        )
        .with_for_update()
    )
    if submittal is None:
        raise SubmittalValidationError("Submittal was not found")
    if submittal.version != expected_version:
        raise SubmittalConflictError("Submittal changed; refresh before voiding")
    if submittal.status in _TERMINAL_STATUSES:
        raise SubmittalConflictError("Closed or already void Submittals cannot be voided")
    submittal.status = SubmittalStatus.VOID
    submittal.ball_in_court_membership_id = None
    submittal.version += 1
    await db.flush()
    await _history(
        db,
        submittal=submittal,
        event_type=SubmittalHistoryType.VOIDED,
        actor_user_id=actor_user_id,
        summary=f"Submittal voided: {reason_text}",
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="submittal.voided",
        target_type="submittal",
        target_id=str(submittal.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        risk=AuditRisk.HIGH,
        changes={"reason": reason_text, "number": submittal.number},
    )
    await _publish_change(
        db,
        submittal=submittal,
        event_type="submittal.voided",
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    return submittal
