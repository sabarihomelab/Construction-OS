import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.files.generated import store_generated_file
from app.modules.reporting.template_models import ReportRenderRecord, TemplateOutputFormat
from app.modules.reporting.template_provider import report_data_providers, resolve_path
from app.modules.reporting.template_renderer import render_report
from app.modules.reporting.template_schemas import ReportLayoutSpec
from app.modules.reporting.template_service import resolve_template_version
from app.modules.reporting.type_registry import ReportGenerationTrigger, report_types


class ReportIssuanceError(ValueError):
    pass


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return normalized or "report"


def _render_filename_pattern(pattern: str, payload: dict[str, object]) -> str:
    result = pattern
    for path in re.findall(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", pattern):
        value = resolve_path(payload, path)
        result = re.sub(
            r"\{\{\s*" + re.escape(path) + r"\s*\}\}",
            "" if value is None else str(value),
            result,
        )
    return _safe_filename(result)


async def issue_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    source_entity_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None,
    output_format: TemplateOutputFormat,
    generation_trigger: ReportGenerationTrigger,
    template_version_id: UUID | None = None,
) -> tuple[bytes, str, str, ReportRenderRecord]:
    report_type = report_types.get(report_type_key)
    if not report_type.stores_issued_output:
        raise ReportIssuanceError(f"{report_type.name} does not store issued outputs")
    if output_format.value not in report_type.issued_output_formats:
        raise ReportIssuanceError(
            f"Issued {report_type.name} output format must be one of: "
            f"{', '.join(report_type.issued_output_formats)}"
        )
    if generation_trigger not in report_type.allowed_triggers:
        raise ReportIssuanceError(
            f"Generation trigger {generation_trigger.value!r} is not allowed for {report_type.name}"
        )

    provider = report_data_providers.get(report_type_key)
    payload = await provider.build_payload(db, organization_id, project_id, source_entity_id)
    template_version = await resolve_template_version(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_type_key=report_type_key,
        actor_user_id=actor_user_id,
        explicit_version_id=template_version_id,
    )
    layout = ReportLayoutSpec.model_validate(template_version.layout_spec)
    content, content_type, extension = render_report(payload, layout, output_format)
    source_revision_value = resolve_path(payload, provider.contract.source_revision_path)
    try:
        source_revision = int(str(source_revision_value))
    except (TypeError, ValueError) as exc:
        raise ReportIssuanceError(
            f"Report provider did not expose a valid source revision at "
            f"{provider.contract.source_revision_path}"
        ) from exc

    filename_base = _render_filename_pattern(report_type.filename_pattern, payload)
    filename = f"{filename_base}.{extension}"
    asset, file_version = await store_generated_file(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        filename=filename,
        content=content,
        content_type=content_type,
        source_system=f"reporting:{report_type_key}",
        source_metadata={
            "report_type_key": report_type_key,
            "source_entity_type": provider.source_entity_type,
            "source_entity_id": str(source_entity_id),
            "source_revision": source_revision,
            "template_version_id": str(template_version.id),
            "generation_trigger": generation_trigger.value,
        },
    )
    record = ReportRenderRecord(
        organization_id=organization_id,
        project_id=project_id,
        report_type_key=report_type_key,
        source_entity_type=provider.source_entity_type,
        source_entity_id=source_entity_id,
        source_revision=source_revision,
        template_version_id=template_version.id,
        output_format=output_format,
        generation_trigger=generation_trigger.value,
        payload_snapshot=payload,
        presentation_snapshot=layout.model_dump(mode="json"),
        content_sha256=hashlib.sha256(content).hexdigest(),
        output_filename=filename,
        output_file_asset_id=asset.id,
        output_file_version=file_version.version,
        issued_at=datetime.now(UTC),
        generated_by_user_id=actor_user_id,
    )
    db.add(record)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="reporting.report.issued",
        target_type="report_render_record",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "report_type_key": report_type_key,
            "source_entity_type": provider.source_entity_type,
            "source_entity_id": str(source_entity_id),
            "source_revision": source_revision,
            "template_version_id": str(template_version.id),
            "output_format": output_format.value,
            "output_filename": filename,
            "output_file_asset_id": str(asset.id),
            "output_file_version": file_version.version,
            "generation_trigger": generation_trigger.value,
        },
    )
    return content, content_type, filename, record
