from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drawings.models import (
    DrawingComparison,
    DrawingComparisonStatus,
    DrawingRenderPackage,
    DrawingRevision,
    DrawingRevisionStatus,
    DrawingSet,
    DrawingSheet,
)
from app.modules.drawings.renderer import (
    DrawingComparisonRequest,
    DrawingRenderRequest,
    DrawingRendererRegistry,
)
from app.modules.events.service import enqueue_event
from app.modules.files.models import FileVersion, StorageObject
from app.modules.jobs.handlers import JobHandlerRegistry
from app.modules.jobs.models import BackgroundJob


class DrawingWorkerError(ValueError):
    pass


def _uuid(job: BackgroundJob, key: str) -> UUID:
    raw = job.payload.get(key)
    if not isinstance(raw, str):
        raise DrawingWorkerError(f"Drawing job requires {key}")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise DrawingWorkerError(f"Drawing job contains invalid {key}") from exc


async def _project_id_for_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    revision: DrawingRevision,
) -> UUID:
    project_id = await db.scalar(
        select(DrawingSet.project_id)
        .join(DrawingSheet, DrawingSheet.drawing_set_id == DrawingSet.id)
        .where(
            DrawingSheet.id == revision.sheet_id,
            DrawingSheet.organization_id == organization_id,
            DrawingSet.organization_id == organization_id,
        )
    )
    if project_id is None:
        raise DrawingWorkerError("Drawing revision project was not found")
    return project_id


def register_drawing_handlers(
    jobs: JobHandlerRegistry,
    renderers: DrawingRendererRegistry,
) -> None:
    async def process_revision(db: AsyncSession, job: BackgroundJob) -> dict[str, object]:
        revision_id = _uuid(job, "drawing_revision_id")
        revision = await db.scalar(
            select(DrawingRevision)
            .where(
                DrawingRevision.id == revision_id,
                DrawingRevision.organization_id == job.organization_id,
            )
            .with_for_update()
        )
        if revision is None:
            raise DrawingWorkerError("Drawing revision was not found")
        project_id = await _project_id_for_revision(
            db,
            organization_id=job.organization_id,
            revision=revision,
        )

        file_version = await db.scalar(
            select(FileVersion).where(
                FileVersion.id == revision.file_version_id,
                FileVersion.organization_id == job.organization_id,
            )
        )
        if file_version is None:
            raise DrawingWorkerError("Drawing source file version was not found")
        storage_object = await db.scalar(
            select(StorageObject).where(
                StorageObject.id == file_version.storage_object_id,
                StorageObject.organization_id == job.organization_id,
            )
        )
        if storage_object is None:
            raise DrawingWorkerError("Drawing source storage object was not found")

        renderer = (
            renderers.get(revision.renderer_key) if revision.renderer_key else renderers.default()
        )
        revision.status = DrawingRevisionStatus.PROCESSING
        await db.flush()
        try:
            result = await renderer.render(
                DrawingRenderRequest(
                    organization_id=str(job.organization_id),
                    drawing_revision_id=str(revision.id),
                    source_provider_key=storage_object.provider_key,
                    source_storage_key=storage_object.storage_key,
                    source_page=revision.source_page,
                    render_version=revision.render_version,
                )
            )
        except Exception:
            revision.status = DrawingRevisionStatus.FAILED
            await db.flush()
            raise

        package = await db.scalar(
            select(DrawingRenderPackage).where(
                DrawingRenderPackage.drawing_revision_id == revision.id,
                DrawingRenderPackage.render_version == revision.render_version,
            )
        )
        if package is None:
            package = DrawingRenderPackage(
                organization_id=job.organization_id,
                drawing_revision_id=revision.id,
                render_version=revision.render_version,
            )
            db.add(package)
        package.manifest = result.manifest
        package.completed_at = datetime.now(UTC)
        revision.renderer_key = result.renderer_key
        revision.page_width = result.page_width
        revision.page_height = result.page_height
        revision.geometry_metadata = result.geometry_metadata
        revision.status = DrawingRevisionStatus.READY
        await db.flush()
        await enqueue_event(
            db,
            organization_id=job.organization_id,
            event_type="drawing.revision.ready",
            entity_type="drawing_revision",
            entity_id=revision.id,
            entity_version=revision.render_version,
            required_permission_key="drawings.drawing.view",
            scope_type="project",
            scope_id=project_id,
            payload={"render_version": revision.render_version},
        )
        return {"drawing_revision_id": str(revision.id), "render_version": revision.render_version}

    async def compare_revisions(db: AsyncSession, job: BackgroundJob) -> dict[str, object]:
        comparison_id = _uuid(job, "comparison_id")
        comparison = await db.scalar(
            select(DrawingComparison)
            .where(
                DrawingComparison.id == comparison_id,
                DrawingComparison.organization_id == job.organization_id,
            )
            .with_for_update()
        )
        if comparison is None:
            raise DrawingWorkerError("Drawing comparison was not found")

        base_revision = await db.scalar(
            select(DrawingRevision).where(
                DrawingRevision.id == comparison.base_revision_id,
                DrawingRevision.organization_id == job.organization_id,
            )
        )
        compare_revision = await db.scalar(
            select(DrawingRevision).where(
                DrawingRevision.id == comparison.compare_revision_id,
                DrawingRevision.organization_id == job.organization_id,
            )
        )
        if base_revision is None or compare_revision is None:
            raise DrawingWorkerError("Drawing comparison revision was not found")
        if base_revision.sheet_id != compare_revision.sheet_id:
            raise DrawingWorkerError("Drawing comparison revisions must belong to the same sheet")

        base_package = await db.scalar(
            select(DrawingRenderPackage).where(
                DrawingRenderPackage.drawing_revision_id == base_revision.id,
                DrawingRenderPackage.render_version == base_revision.render_version,
            )
        )
        compare_package = await db.scalar(
            select(DrawingRenderPackage).where(
                DrawingRenderPackage.drawing_revision_id == compare_revision.id,
                DrawingRenderPackage.render_version == compare_revision.render_version,
            )
        )
        if base_package is None or compare_package is None:
            raise DrawingWorkerError("Both drawing render packages must be ready before comparison")

        renderer_key = compare_revision.renderer_key or base_revision.renderer_key
        renderer = renderers.get(renderer_key) if renderer_key else renderers.default()
        comparison.status = DrawingComparisonStatus.PROCESSING
        await db.flush()
        try:
            result = await renderer.compare(
                DrawingComparisonRequest(
                    organization_id=str(job.organization_id),
                    comparison_id=str(comparison.id),
                    base_manifest=base_package.manifest,
                    compare_manifest=compare_package.manifest,
                )
            )
        except Exception as exc:
            comparison.status = DrawingComparisonStatus.FAILED
            comparison.error_message = str(exc)[:1000]
            await db.flush()
            raise
        comparison.alignment = result.alignment
        comparison.result_manifest = result.result_manifest
        comparison.status = DrawingComparisonStatus.READY
        comparison.completed_at = datetime.now(UTC)
        comparison.error_message = None
        await db.flush()
        return {"comparison_id": str(comparison.id), "status": comparison.status.value}

    if not jobs.contains("drawings.process_revision"):
        jobs.register(
            "drawings.process_revision",
            process_revision,
            timeout_seconds=900,
            lease_seconds=120,
        )
    if not jobs.contains("drawings.compare_revisions"):
        jobs.register(
            "drawings.compare_revisions",
            compare_revisions,
            timeout_seconds=900,
            lease_seconds=120,
        )
