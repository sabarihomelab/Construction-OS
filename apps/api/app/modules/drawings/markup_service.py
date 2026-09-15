from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.drawings.models import DrawingMarkup, DrawingMarkupType, DrawingRevision
from app.modules.events.service import enqueue_event


class DrawingMarkupValidationError(ValueError):
    pass


class DrawingMarkupConflictError(ValueError):
    pass


def _validate_geometry(geometry: dict[str, object]) -> None:
    if not geometry:
        raise DrawingMarkupValidationError("Markup geometry is required")
    if len(str(geometry)) > 100_000:
        raise DrawingMarkupValidationError("Markup geometry is too large")


async def create_markup(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    drawing_revision_id: UUID,
    markup_type: DrawingMarkupType,
    geometry: dict[str, object],
    actor_user_id: UUID,
    style: dict[str, object] | None = None,
    text: str | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> DrawingMarkup:
    _validate_geometry(geometry)
    revision = await db.scalar(
        select(DrawingRevision.id).where(
            DrawingRevision.id == drawing_revision_id,
            DrawingRevision.organization_id == organization_id,
        )
    )
    if revision is None:
        raise DrawingMarkupValidationError("Drawing revision was not found")
    markup = DrawingMarkup(
        organization_id=organization_id,
        drawing_revision_id=drawing_revision_id,
        markup_type=markup_type,
        geometry=geometry,
        style=style or {},
        text=text,
        created_by_user_id=actor_user_id,
    )
    db.add(markup)
    await db.flush()
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="drawing.markup.created",
        entity_type="drawing_markup",
        entity_id=markup.id,
        entity_version=markup.version,
        required_permission_key="drawings.drawing.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"drawing_revision_id": str(drawing_revision_id), "version": markup.version},
    )
    return markup


async def update_markup(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    markup_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    geometry: dict[str, object] | None = None,
    style: dict[str, object] | None = None,
    text: str | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> DrawingMarkup:
    markup = await db.scalar(
        select(DrawingMarkup)
        .where(DrawingMarkup.id == markup_id, DrawingMarkup.organization_id == organization_id)
        .with_for_update()
    )
    if markup is None or markup.deleted_at is not None:
        raise DrawingMarkupValidationError("Drawing markup was not found")
    if markup.version != expected_version:
        raise DrawingMarkupConflictError("Drawing markup changed; refresh before saving")
    if geometry is not None:
        _validate_geometry(geometry)
        markup.geometry = geometry
    if style is not None:
        markup.style = style
    if text is not None:
        markup.text = text
    markup.version += 1
    await db.flush()
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="drawing.markup.updated",
        entity_type="drawing_markup",
        entity_id=markup.id,
        entity_version=markup.version,
        required_permission_key="drawings.drawing.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"drawing_revision_id": str(markup.drawing_revision_id), "version": markup.version},
    )
    return markup


async def retire_markup(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    markup_id: UUID,
    expected_version: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> DrawingMarkup:
    markup = await db.scalar(
        select(DrawingMarkup)
        .where(DrawingMarkup.id == markup_id, DrawingMarkup.organization_id == organization_id)
        .with_for_update()
    )
    if markup is None:
        raise DrawingMarkupValidationError("Drawing markup was not found")
    if markup.version != expected_version:
        raise DrawingMarkupConflictError("Drawing markup changed; refresh before retiring")
    if markup.deleted_at is not None:
        return markup
    markup.deleted_at = datetime.now(UTC)
    markup.version += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="drawing.markup.retired",
        target_type="drawing_markup",
        target_id=str(markup.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        changes={"drawing_revision_id": str(markup.drawing_revision_id), "version": markup.version},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="drawing.markup.retired",
        entity_type="drawing_markup",
        entity_id=markup.id,
        entity_version=markup.version,
        required_permission_key="drawings.drawing.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"drawing_revision_id": str(markup.drawing_revision_id), "version": markup.version},
    )
    return markup
