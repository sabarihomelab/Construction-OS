import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reporting.template_execution import render_template_version
from app.modules.reporting.template_models import TemplateOutputFormat
from app.modules.reporting.template_provider import report_data_providers, resolve_path
from app.modules.reporting.template_schemas import ReportLayoutSpec
from app.modules.reporting.template_service import resolve_template_version
from app.modules.reporting.type_registry import report_types


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return normalized or "report-preview"


def _preview_name(pattern: str, payload: dict[str, object], extension: str) -> str:
    value = pattern
    for path in re.findall(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", pattern):
        replacement = resolve_path(payload, path)
        value = re.sub(
            r"\{\{\s*" + re.escape(path) + r"\s*\}\}",
            "" if replacement is None else str(replacement),
            value,
        )
    return f"{_safe_filename(value)}-PREVIEW.{extension}"


async def preview_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    source_entity_id: UUID,
    actor_user_id: UUID,
    output_format: TemplateOutputFormat,
    template_version_id: UUID | None = None,
) -> tuple[bytes, str, str]:
    provider = report_data_providers.get(report_type_key)
    payload = await provider.build_payload(db, organization_id, project_id, source_entity_id)
    version = await resolve_template_version(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_type_key=report_type_key,
        actor_user_id=actor_user_id,
        explicit_version_id=template_version_id,
    )
    layout = ReportLayoutSpec.model_validate(version.layout_spec)
    content, content_type, extension = await render_template_version(
        db,
        organization_id=organization_id,
        template_version=version,
        payload=payload,
        layout=layout,
        output_format=output_format,
    )
    report_type = report_types.get(report_type_key)
    return content, content_type, _preview_name(report_type.filename_pattern, payload, extension)
