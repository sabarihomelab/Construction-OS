from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field import dpr_provider as _dpr_provider  # noqa: F401
from app.modules.field import dpr_report_type as _dpr_report_type  # noqa: F401
from app.modules.field.dpr_custom_field_service import (
    materialize_and_validate_required_dpr_custom_fields,
)
from app.modules.field.dpr_report_type import DPR_REPORT_TYPE_KEY
from app.modules.field.dpr_service import DPRValidationError
from app.modules.field.models import DailyReport, DailyReportStatus
from app.modules.field.service import DailyReportValidationError
from app.modules.jobs.handlers import JobHandlerRegistry
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.service import enqueue_job
from app.modules.reporting.issuance import issue_report
from app.modules.reporting.template_models import ReportRenderRecord, TemplateOutputFormat
from app.modules.reporting.type_registry import ReportGenerationTrigger, report_types

DPR_APPROVAL_JOB_TYPE = "reporting.issue_dpr_on_approval"


class DPRReportJobError(ValueError):
    pass


def _payload_uuid(job: BackgroundJob, key: str) -> UUID:
    value = job.payload.get(key)
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise DPRReportJobError(f"DPR report job requires a valid {key}") from exc


def _payload_revision(job: BackgroundJob) -> int:
    value = job.payload.get("source_revision")
    if not isinstance(value, int) or value < 1:
        raise DPRReportJobError("DPR report job requires a positive source_revision")
    return value


def dpr_approval_idempotency_key(report_id: UUID, revision: int, output_format: str) -> str:
    return f"dpr-approval:{report_id}:{revision}:{output_format}"


async def enqueue_dpr_approval_report(
    db: AsyncSession,
    *,
    report: DailyReport,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> BackgroundJob | None:
    try:
        await materialize_and_validate_required_dpr_custom_fields(
            db,
            organization_id=report.organization_id,
            report=report,
            actor_user_id=actor_user_id,
        )
    except DPRValidationError as exc:
        raise DailyReportValidationError(str(exc)) from exc

    contract = report_types.get(DPR_REPORT_TYPE_KEY)
    if not contract.stores_issued_output:
        return None
    if contract.default_trigger != ReportGenerationTrigger.ON_APPROVAL:
        return None
    if ReportGenerationTrigger.ON_APPROVAL not in contract.allowed_triggers:
        return None
    if report.status != DailyReportStatus.APPROVED:
        return None

    output_format = contract.default_output_format
    return await enqueue_job(
        db,
        organization_id=report.organization_id,
        job_type=DPR_APPROVAL_JOB_TYPE,
        payload={
            "project_id": str(report.project_id),
            "report_id": str(report.id),
            "source_revision": report.revision,
            "output_format": output_format,
            "actor_user_id": str(actor_user_id),
            "session_id": str(session_id) if session_id else None,
        },
        idempotency_key=dpr_approval_idempotency_key(report.id, report.revision, output_format),
        priority=20,
        max_attempts=5,
        created_by_user_id=actor_user_id,
        correlation_id=session_id,
    )


async def issue_dpr_on_approval(db: AsyncSession, job: BackgroundJob) -> dict[str, object]:
    project_id = _payload_uuid(job, "project_id")
    report_id = _payload_uuid(job, "report_id")
    source_revision = _payload_revision(job)
    actor_user_id = _payload_uuid(job, "actor_user_id")
    session_value = job.payload.get("session_id")
    session_id = UUID(str(session_value)) if session_value else None

    raw_format = job.payload.get("output_format")
    try:
        output_format = TemplateOutputFormat(str(raw_format))
    except ValueError as exc:
        raise DPRReportJobError("DPR report job has an unsupported output_format") from exc

    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == job.organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        return {"issued": False, "skipped": True, "reason": "source_report_missing"}
    if report.status != DailyReportStatus.APPROVED:
        return {"issued": False, "skipped": True, "reason": "source_report_not_approved"}
    if report.revision != source_revision:
        return {
            "issued": False,
            "skipped": True,
            "reason": "source_revision_changed",
            "current_revision": report.revision,
        }

    existing = await db.scalar(
        select(ReportRenderRecord)
        .where(
            ReportRenderRecord.organization_id == job.organization_id,
            ReportRenderRecord.project_id == project_id,
            ReportRenderRecord.report_type_key == DPR_REPORT_TYPE_KEY,
            ReportRenderRecord.source_entity_id == report_id,
            ReportRenderRecord.source_revision == source_revision,
            ReportRenderRecord.output_format == output_format,
            ReportRenderRecord.generation_trigger == ReportGenerationTrigger.ON_APPROVAL.value,
        )
        .order_by(ReportRenderRecord.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        return {
            "issued": True,
            "reused": True,
            "render_id": str(existing.id),
            "filename": existing.output_filename,
        }

    _content, _content_type, filename, record = await issue_report(
        db,
        organization_id=job.organization_id,
        project_id=project_id,
        report_type_key=DPR_REPORT_TYPE_KEY,
        source_entity_id=report_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        output_format=output_format,
        generation_trigger=ReportGenerationTrigger.ON_APPROVAL,
    )
    return {
        "issued": True,
        "reused": False,
        "render_id": str(record.id),
        "filename": filename,
        "output_format": output_format.value,
        "source_revision": source_revision,
    }


def register_dpr_report_handlers(jobs: JobHandlerRegistry) -> None:
    if jobs.contains(DPR_APPROVAL_JOB_TYPE):
        return
    jobs.register(
        DPR_APPROVAL_JOB_TYPE,
        issue_dpr_on_approval,
        timeout_seconds=300,
        lease_seconds=360,
        profile="reporting",
        module_key="field",
    )
