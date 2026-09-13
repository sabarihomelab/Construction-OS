from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field.dpr_jobs import (
    DPR_APPROVAL_JOB_TYPE,
    dpr_approval_idempotency_key,
)
from app.modules.field.dpr_report_type import DPR_REPORT_TYPE_KEY
from app.modules.field.models import DailyReport, DailyReportStatus
from app.modules.jobs.models import BackgroundJob
from app.modules.projects.access import project_permission_is_allowed
from app.modules.reporting.template_models import ReportRenderRecord, TemplateOutputFormat
from app.modules.reporting.type_registry import ReportGenerationTrigger, report_types
from app.modules.sessions.deps import CurrentSession

router = APIRouter(tags=["daily-progress-reports"])


class DPRGenerationStatusRead(BaseModel):
    report_id: UUID
    source_revision: int
    report_status: str
    generation_state: str
    output_format: str
    job_id: UUID | None = None
    job_status: str | None = None
    failure_code: str | None = None
    render_id: UUID | None = None
    filename: str | None = None
    issued_at: datetime | None = None
    download_path: str | None = None


def _require_permission(context, project_id: UUID) -> None:
    project_permissions = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        "field.daily_report.view",
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/projects/{project_id}/daily-reports/{report_id}/report-generation",
    response_model=DPRGenerationStatusRead,
)
async def get_dpr_generation_status(
    project_id: UUID,
    report_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DPRGenerationStatusRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id)
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == context.organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily Progress Report not found")

    contract = report_types.get(DPR_REPORT_TYPE_KEY)
    output_format = TemplateOutputFormat(contract.default_output_format)
    render = await db.scalar(
        select(ReportRenderRecord)
        .where(
            ReportRenderRecord.organization_id == context.organization_id,
            ReportRenderRecord.project_id == project_id,
            ReportRenderRecord.report_type_key == DPR_REPORT_TYPE_KEY,
            ReportRenderRecord.source_entity_id == report_id,
            ReportRenderRecord.source_revision == report.revision,
            ReportRenderRecord.output_format == output_format,
            ReportRenderRecord.generation_trigger == ReportGenerationTrigger.ON_APPROVAL.value,
        )
        .order_by(ReportRenderRecord.created_at.desc())
        .limit(1)
    )
    if render is not None:
        return DPRGenerationStatusRead(
            report_id=report.id,
            source_revision=report.revision,
            report_status=report.status.value,
            generation_state="issued",
            output_format=output_format.value,
            render_id=render.id,
            filename=render.output_filename,
            issued_at=render.issued_at,
            download_path=(
                f"/api/v1/projects/{project_id}/daily-reports/{report_id}/"
                f"render-history/{render.id}/download"
            ),
        )

    if report.status != DailyReportStatus.APPROVED:
        return DPRGenerationStatusRead(
            report_id=report.id,
            source_revision=report.revision,
            report_status=report.status.value,
            generation_state="not_ready",
            output_format=output_format.value,
        )

    key = dpr_approval_idempotency_key(report.id, report.revision, output_format.value)
    job = await db.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.organization_id == context.organization_id,
            BackgroundJob.job_type == DPR_APPROVAL_JOB_TYPE,
            BackgroundJob.idempotency_key == key,
        )
        .order_by(BackgroundJob.created_at.desc())
        .limit(1)
    )
    if job is None:
        return DPRGenerationStatusRead(
            report_id=report.id,
            source_revision=report.revision,
            report_status=report.status.value,
            generation_state="not_queued",
            output_format=output_format.value,
        )

    return DPRGenerationStatusRead(
        report_id=report.id,
        source_revision=report.revision,
        report_status=report.status.value,
        generation_state=job.status.value,
        output_format=output_format.value,
        job_id=job.id,
        job_status=job.status.value,
        failure_code=job.last_error_code if job.status.value == "failed" else None,
    )
