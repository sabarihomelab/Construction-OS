from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.files.models import FileProcessingStatus, FileScanStatus, FileVersion
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index
from app.modules.documents.models import (
    Document,
    DocumentKind,
    DocumentRevision,
    DocumentRevisionStatus,
    DocumentStatus,
    SpecificationSection,
)


class DocumentValidationError(ValueError):
    pass


class DocumentConflictError(ValueError):
    pass


async def create_document(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> Document:
    project_exists = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project_exists is None:
        raise DocumentValidationError("Project was not found")

    number = str(values.get("number") or "").strip()
    title = str(values.get("title") or "").strip()
    if not number or not title:
        raise DocumentValidationError("Document number and title are required")

    existing = await db.scalar(
        select(Document.id).where(Document.project_id == project_id, Document.number == number)
    )
    if existing is not None:
        raise DocumentConflictError("Document number already exists in this project")

    data = dict(values)
    data.pop("organization_id", None)
    data.pop("project_id", None)
    data["number"] = number
    data["title"] = title
    document = Document(
        organization_id=organization_id,
        project_id=project_id,
        created_by_user_id=actor_user_id,
        **data,
    )
    db.add(document)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="document.created",
        target_type="document",
        target_id=str(document.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        changes={"after": {"project_id": str(project_id), "number": number, "title": title}},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="document.created",
        entity_type="document",
        entity_id=document.id,
        entity_version=document.version,
        required_permission_key="documents.document.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"version": document.version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="document",
        entity_id=document.id,
        entity_version=document.version,
        correlation_id=correlation_id,
    )
    return document


async def add_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    document_id: UUID,
    revision_label: str,
    file_version_id: UUID,
    actor_user_id: UUID,
    notes: str | None = None,
) -> DocumentRevision:
    document = await db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.organization_id == organization_id)
        .with_for_update()
    )
    if document is None:
        raise DocumentValidationError("Document was not found")

    file_version = await db.scalar(
        select(FileVersion).where(
            FileVersion.id == file_version_id,
            FileVersion.organization_id == organization_id,
        )
    )
    if file_version is None:
        raise DocumentValidationError("File version was not found")

    label = revision_label.strip()
    if not label:
        raise DocumentValidationError("Revision label is required")
    duplicate = await db.scalar(
        select(DocumentRevision.id).where(
            DocumentRevision.document_id == document_id,
            DocumentRevision.revision_label == label,
        )
    )
    if duplicate is not None:
        raise DocumentConflictError("Revision label already exists for this document")

    next_sequence = document.current_revision_sequence + 1
    revision = DocumentRevision(
        organization_id=organization_id,
        document_id=document_id,
        sequence=next_sequence,
        revision_label=label,
        file_version_id=file_version_id,
        notes=notes,
        created_by_user_id=actor_user_id,
    )
    db.add(revision)
    document.current_revision_sequence = next_sequence
    document.version += 1
    await db.flush()
    return revision


async def publish_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    revision_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    issue_date=None,
) -> DocumentRevision:
    revision = await db.scalar(
        select(DocumentRevision)
        .where(
            DocumentRevision.id == revision_id,
            DocumentRevision.organization_id == organization_id,
        )
        .with_for_update()
    )
    if revision is None:
        raise DocumentValidationError("Document revision was not found")
    if revision.status != DocumentRevisionStatus.DRAFT:
        raise DocumentConflictError("Only draft document revisions can be published")

    file_version = await db.scalar(
        select(FileVersion).where(
            FileVersion.id == revision.file_version_id,
            FileVersion.organization_id == organization_id,
        )
    )
    if file_version is None:
        raise DocumentValidationError("Revision file version was not found")
    if file_version.scan_status != FileScanStatus.CLEAN:
        raise DocumentValidationError("Document cannot be published until the file scan is clean")
    if file_version.processing_status != FileProcessingStatus.READY:
        raise DocumentValidationError("Document cannot be published until file processing is ready")

    document = await db.scalar(
        select(Document)
        .where(
            Document.id == revision.document_id,
            Document.organization_id == organization_id,
        )
        .with_for_update()
    )
    if document is None:
        raise DocumentValidationError("Document was not found")

    previous_rows = await db.scalars(
        select(DocumentRevision).where(
            DocumentRevision.document_id == document.id,
            DocumentRevision.status == DocumentRevisionStatus.PUBLISHED,
        )
    )
    for previous in previous_rows.all():
        previous.status = DocumentRevisionStatus.SUPERSEDED

    now = datetime.now(UTC)
    revision.status = DocumentRevisionStatus.PUBLISHED
    revision.published_by_user_id = actor_user_id
    revision.published_at = now
    revision.issue_date = issue_date
    document.status = DocumentStatus.ACTIVE
    document.version += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="document.revision.published",
        target_type="document_revision",
        target_id=str(revision.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.HIGH,
        changes={
            "document_id": str(document.id),
            "revision_label": revision.revision_label,
            "sequence": revision.sequence,
            "file_version_id": str(revision.file_version_id),
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="document.revision.published",
        entity_type="document",
        entity_id=document.id,
        entity_version=document.version,
        required_permission_key="documents.document.view",
        scope_type="project",
        scope_id=document.project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"revision_label": revision.revision_label, "version": document.version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="document",
        entity_id=document.id,
        entity_version=document.version,
        correlation_id=correlation_id,
    )
    return revision


async def add_specification_section(
    db: AsyncSession,
    *,
    organization_id: UUID,
    document_id: UUID,
    section_number: str,
    title: str,
    division_code: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> SpecificationSection:
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )
    if document is None or document.kind != DocumentKind.SPECIFICATION:
        raise DocumentValidationError("Specification sections require a specification document")
    if page_start is not None and page_end is not None and page_end < page_start:
        raise DocumentValidationError("Specification page_end cannot be before page_start")

    section = SpecificationSection(
        organization_id=organization_id,
        document_id=document_id,
        section_number=section_number.strip(),
        title=title.strip(),
        division_code=division_code.strip() if division_code else None,
        page_start=page_start,
        page_end=page_end,
    )
    if not section.section_number or not section.title:
        raise DocumentValidationError("Specification section number and title are required")
    db.add(section)
    document.version += 1
    await db.flush()
    return section
