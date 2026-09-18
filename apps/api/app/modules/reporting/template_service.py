import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.files.models import FileAsset, FileAssetStatus, FileVersion
from app.modules.reporting.template_api_schemas import ReportBrandingUpdate
from app.modules.reporting.template_models import (
    ReportBrandingProfile,
    ReportRenderRecord,
    ReportTemplate,
    ReportTemplateVersion,
    TemplateOutputFormat,
    TemplateSourceKind,
    TemplateVersionStatus,
)
from app.modules.reporting.template_provider import (
    ReportDataProvider,
    ReportTemplateValidationError,
    report_data_providers,
    resolve_path,
    validate_layout_against_contract,
)
from app.modules.reporting.template_renderer import render_report
from app.modules.reporting.template_schemas import (
    ConditionOperator,
    DisplayCondition,
    HeaderFooterSpec,
    PageSpec,
    ReportBlock,
    ReportBlockKind,
    ReportLayoutSpec,
    ReportTemplateCreate,
    ReportTemplateVersionCreate,
    TableColumnSpec,
)


class ReportTemplateConflictError(ValueError):
    pass


def _default_title(provider: ReportDataProvider) -> str:
    leaf = provider.contract.key.split(".")[-1].replace("_", " ").strip()
    return " ".join(part.upper() if part.lower() == "dpr" else part.title() for part in leaf.split())


def _automatic_default_layout(provider: ReportDataProvider) -> ReportLayoutSpec:
    scalar_candidates = [
        path
        for path in (
            "company.name",
            "project.name",
            "project.client_name",
            "report.number",
            "report.date",
            "report.shift",
            "report.weather_condition",
            "summary.total_workers",
            "summary.total_labour_hours",
        )
        if provider.contract.path_allowed(path)
    ]
    blocks: list[ReportBlock] = []
    order = 10
    if provider.contract.path_allowed("company.logo"):
        blocks.append(
            ReportBlock(
                id="company-logo",
                kind=ReportBlockKind.IMAGE,
                order=order,
                row=0,
                width_percent=25,
                image_placeholder="company.logo",
                hide_when_empty=True,
            )
        )
        order += 10
    if scalar_candidates:
        blocks.append(
            ReportBlock(
                id="report-summary",
                kind=ReportBlockKind.FIELD_GROUP,
                order=order,
                row=0,
                width_percent=75 if provider.contract.path_allowed("company.logo") else 100,
                title="Report Details",
                scalar_fields=scalar_candidates,
            )
        )
        order += 10
    row_number = 1
    for collection in provider.contract.collections:
        columns = [
            TableColumnSpec(key=field, order=index * 10)
            for index, field in enumerate(collection.fields[:12], start=1)
        ]
        blocks.append(
            ReportBlock(
                id=f"section-{collection.key}",
                kind=ReportBlockKind.TABLE,
                order=order,
                row=row_number,
                width_percent=100,
                title=collection.key.replace("_", " ").title(),
                data_key=collection.key,
                table_columns=columns,
                condition=DisplayCondition(
                    path=collection.key,
                    operator=ConditionOperator.NON_EMPTY,
                ),
                hide_when_empty=True,
                repeat_table_header=True,
                avoid_row_split=True,
                keep_title_with_content=True,
            )
        )
        order += 10
        row_number += 1
    if provider.contract.path_allowed("approvals.prepared_by"):
        blocks.append(
            ReportBlock(
                id="signatures",
                kind=ReportBlockKind.SIGNATURES,
                order=order,
                row=row_number,
                width_percent=100,
                title="Prepared / Reviewed / Approved",
                data_key="approvals",
                hide_when_empty=True,
            )
        )
    return ReportLayoutSpec(
        report_title=f"{{{{project.name}}}} - {_default_title(provider)}"
        if provider.contract.path_allowed("project.name")
        else _default_title(provider),
        page=PageSpec(),
        header_footer=HeaderFooterSpec(
            header_left="{{company.name}}" if provider.contract.path_allowed("company.name") else None,
            header_right="{{report.number}}" if provider.contract.path_allowed("report.number") else None,
            footer_left="{{project.name}}" if provider.contract.path_allowed("project.name") else None,
            show_page_number=True,
        ),
        blocks=blocks,
    )


def provider_default_layout(provider: ReportDataProvider) -> ReportLayoutSpec:
    layout = provider.default_layout() if provider.default_layout else _automatic_default_layout(provider)
    validate_layout_against_contract(layout, provider.contract)
    return layout


async def _validate_file_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    asset_id: UUID,
    version: int,
) -> FileVersion:
    row = await db.scalar(
        select(FileVersion)
        .join(FileAsset, FileAsset.id == FileVersion.asset_id)
        .where(
            FileVersion.organization_id == organization_id,
            FileVersion.asset_id == asset_id,
            FileVersion.version == version,
            FileAsset.organization_id == organization_id,
            FileAsset.status == FileAssetStatus.ACTIVE,
        )
    )
    if row is None:
        raise ReportTemplateValidationError("Active File Asset version was not found")
    return row


async def get_branding(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> ReportBrandingProfile | None:
    return await db.scalar(
        select(ReportBrandingProfile).where(ReportBrandingProfile.organization_id == organization_id)
    )


async def update_branding(
    db: AsyncSession,
    *,
    organization_id: UUID,
    payload: ReportBrandingUpdate,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ReportBrandingProfile:
    row = await db.scalar(
        select(ReportBrandingProfile)
        .where(ReportBrandingProfile.organization_id == organization_id)
        .with_for_update()
    )
    if row is None:
        if payload.expected_revision != 1:
            raise ReportTemplateConflictError("Branding has not been created; expected_revision must be 1")
        row = ReportBrandingProfile(
            organization_id=organization_id,
            revision=1,
            updated_by_user_id=actor_user_id,
        )
        db.add(row)
        before = None
    else:
        if row.revision != payload.expected_revision:
            raise ReportTemplateConflictError(
                f"Branding changed from revision {payload.expected_revision} to {row.revision}; refresh before saving"
            )
        before = {
            "company_display_name": row.company_display_name,
            "company_logo_asset_id": str(row.company_logo_asset_id) if row.company_logo_asset_id else None,
            "company_logo_version": row.company_logo_version,
            "default_header_text": row.default_header_text,
            "default_footer_text": row.default_footer_text,
            "revision": row.revision,
        }
        row.revision += 1
    if (payload.company_logo_asset_id is None) != (payload.company_logo_version is None):
        raise ReportTemplateValidationError(
            "company_logo_asset_id and company_logo_version must be supplied together"
        )
    if payload.company_logo_asset_id and payload.company_logo_version:
        await _validate_file_version(
            db,
            organization_id=organization_id,
            asset_id=payload.company_logo_asset_id,
            version=payload.company_logo_version,
        )
    row.company_display_name = (
        payload.company_display_name.strip() if payload.company_display_name else None
    )
    row.company_logo_asset_id = payload.company_logo_asset_id
    row.company_logo_version = payload.company_logo_version
    row.default_header_text = (
        payload.default_header_text.strip() if payload.default_header_text else None
    )
    row.default_footer_text = (
        payload.default_footer_text.strip() if payload.default_footer_text else None
    )
    row.updated_by_user_id = actor_user_id
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="reporting.branding.updated",
        target_type="report_branding_profile",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "before": before,
            "after": {
                "company_display_name": row.company_display_name,
                "company_logo_asset_id": str(row.company_logo_asset_id) if row.company_logo_asset_id else None,
                "company_logo_version": row.company_logo_version,
                "default_header_text": row.default_header_text,
                "default_footer_text": row.default_footer_text,
                "revision": row.revision,
            },
        },
    )
    return row


async def list_templates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
) -> list[ReportTemplate]:
    report_data_providers.get(report_type_key)
    rows = await db.scalars(
        select(ReportTemplate)
        .where(
            ReportTemplate.organization_id == organization_id,
            ReportTemplate.report_type_key == report_type_key,
            ReportTemplate.active.is_(True),
            or_(ReportTemplate.project_id == project_id, ReportTemplate.project_id.is_(None)),
        )
        .order_by(
            ReportTemplate.project_id.desc().nullslast(),
            ReportTemplate.is_default.desc(),
            ReportTemplate.name,
        )
    )
    return list(rows.all())


async def create_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    payload: ReportTemplateCreate,
    actor_user_id: UUID,
) -> ReportTemplate:
    report_data_providers.get(report_type_key)
    target_project_id = None if payload.company_wide else project_id
    if payload.is_default:
        defaults = await db.scalars(
            select(ReportTemplate).where(
                ReportTemplate.organization_id == organization_id,
                ReportTemplate.report_type_key == report_type_key,
                ReportTemplate.active.is_(True),
                ReportTemplate.is_default.is_(True),
                ReportTemplate.project_id.is_(None)
                if target_project_id is None
                else ReportTemplate.project_id == target_project_id,
            )
        )
        for item in defaults.all():
            item.is_default = False
    row = ReportTemplate(
        organization_id=organization_id,
        report_type_key=report_type_key,
        project_id=target_project_id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        active=True,
        is_default=payload.is_default,
        current_version=0,
        created_by_user_id=actor_user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _load_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    template_id: UUID,
    for_update: bool = False,
) -> ReportTemplate:
    query = select(ReportTemplate).where(
        ReportTemplate.id == template_id,
        ReportTemplate.organization_id == organization_id,
        ReportTemplate.report_type_key == report_type_key,
        ReportTemplate.active.is_(True),
        or_(ReportTemplate.project_id == project_id, ReportTemplate.project_id.is_(None)),
    )
    if for_update:
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None:
        raise ReportTemplateValidationError("Report template was not found for this project")
    return row


async def list_template_versions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    template_id: UUID,
) -> list[ReportTemplateVersion]:
    template = await _load_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_type_key=report_type_key,
        template_id=template_id,
    )
    rows = await db.scalars(
        select(ReportTemplateVersion)
        .where(
            ReportTemplateVersion.organization_id == organization_id,
            ReportTemplateVersion.template_id == template.id,
        )
        .order_by(ReportTemplateVersion.version.desc())
    )
    return list(rows.all())


async def create_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    template_id: UUID,
    payload: ReportTemplateVersionCreate,
    actor_user_id: UUID,
) -> ReportTemplateVersion:
    provider = report_data_providers.get(report_type_key)
    template = await _load_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_type_key=report_type_key,
        template_id=template_id,
        for_update=True,
    )
    validate_layout_against_contract(payload.layout, provider.contract)
    if payload.source_file_asset_id and payload.source_file_version:
        await _validate_file_version(
            db,
            organization_id=organization_id,
            asset_id=payload.source_file_asset_id,
            version=payload.source_file_version,
        )
    latest = await db.scalar(
        select(ReportTemplateVersion.version)
        .where(
            ReportTemplateVersion.organization_id == organization_id,
            ReportTemplateVersion.template_id == template.id,
        )
        .order_by(ReportTemplateVersion.version.desc())
        .limit(1)
    )
    row = ReportTemplateVersion(
        organization_id=organization_id,
        template_id=template.id,
        version=int(latest or 0) + 1,
        status=TemplateVersionStatus.DRAFT,
        source_kind=payload.source_kind,
        source_file_asset_id=payload.source_file_asset_id,
        source_file_version=payload.source_file_version,
        source_format=payload.source_format.strip().lower() if payload.source_format else None,
        layout_spec=payload.layout.model_dump(mode="json"),
        provider_contract_version=provider.contract.version,
        created_by_user_id=actor_user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def publish_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    template_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ReportTemplateVersion:
    provider = report_data_providers.get(report_type_key)
    template = await _load_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_type_key=report_type_key,
        template_id=template_id,
        for_update=True,
    )
    row = await db.scalar(
        select(ReportTemplateVersion)
        .where(
            ReportTemplateVersion.id == version_id,
            ReportTemplateVersion.organization_id == organization_id,
            ReportTemplateVersion.template_id == template.id,
        )
        .with_for_update()
    )
    if row is None or row.status != TemplateVersionStatus.DRAFT:
        raise ReportTemplateValidationError("Draft template version was not found")
    layout = ReportLayoutSpec.model_validate(row.layout_spec)
    validate_layout_against_contract(layout, provider.contract)
    published = await db.scalars(
        select(ReportTemplateVersion).where(
            ReportTemplateVersion.organization_id == organization_id,
            ReportTemplateVersion.template_id == template.id,
            ReportTemplateVersion.status == TemplateVersionStatus.PUBLISHED,
        )
    )
    for previous in published.all():
        previous.status = TemplateVersionStatus.RETIRED
    row.status = TemplateVersionStatus.PUBLISHED
    row.provider_contract_version = provider.contract.version
    row.published_at = datetime.now(UTC)
    row.published_by_user_id = actor_user_id
    template.current_version = row.version
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="reporting.template.published",
        target_type="report_template_version",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "report_type_key": report_type_key,
            "template_id": str(template.id),
            "version": row.version,
            "project_id": str(template.project_id) if template.project_id else None,
            "provider_contract_version": provider.contract.version,
        },
    )
    return row


async def _ensure_builtin_default(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report_type_key: str,
    actor_user_id: UUID,
) -> ReportTemplateVersion:
    provider = report_data_providers.get(report_type_key)
    template = await db.scalar(
        select(ReportTemplate)
        .where(
            ReportTemplate.organization_id == organization_id,
            ReportTemplate.report_type_key == report_type_key,
            ReportTemplate.project_id.is_(None),
            ReportTemplate.active.is_(True),
            ReportTemplate.is_default.is_(True),
        )
        .order_by(ReportTemplate.created_at, ReportTemplate.id)
        .limit(1)
    )
    if template and template.current_version:
        current = await db.scalar(
            select(ReportTemplateVersion).where(
                ReportTemplateVersion.organization_id == organization_id,
                ReportTemplateVersion.template_id == template.id,
                ReportTemplateVersion.version == template.current_version,
                ReportTemplateVersion.status == TemplateVersionStatus.PUBLISHED,
            )
        )
        if current:
            return current
    if template is None:
        template = ReportTemplate(
            organization_id=organization_id,
            report_type_key=report_type_key,
            project_id=None,
            name="System Default",
            description="Generated from the registered report data contract.",
            active=True,
            is_default=True,
            current_version=0,
            created_by_user_id=actor_user_id,
        )
        db.add(template)
        await db.flush()
    layout = provider_default_layout(provider)
    version_number = max(template.current_version + 1, 1)
    row = ReportTemplateVersion(
        organization_id=organization_id,
        template_id=template.id,
        version=version_number,
        status=TemplateVersionStatus.PUBLISHED,
        source_kind=TemplateSourceKind.BUILTIN,
        layout_spec=layout.model_dump(mode="json"),
        provider_contract_version=provider.contract.version,
        created_by_user_id=actor_user_id,
        published_by_user_id=actor_user_id,
        published_at=datetime.now(UTC),
    )
    db.add(row)
    template.current_version = version_number
    await db.flush()
    return row


async def resolve_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    actor_user_id: UUID,
    explicit_version_id: UUID | None = None,
) -> ReportTemplateVersion:
    report_data_providers.get(report_type_key)
    if explicit_version_id:
        row = await db.scalar(
            select(ReportTemplateVersion)
            .join(ReportTemplate, ReportTemplate.id == ReportTemplateVersion.template_id)
            .where(
                ReportTemplateVersion.id == explicit_version_id,
                ReportTemplateVersion.organization_id == organization_id,
                ReportTemplateVersion.status == TemplateVersionStatus.PUBLISHED,
                ReportTemplate.report_type_key == report_type_key,
                ReportTemplate.active.is_(True),
                or_(ReportTemplate.project_id == project_id, ReportTemplate.project_id.is_(None)),
            )
        )
        if row is None:
            raise ReportTemplateValidationError(
                "Published template version is not available to this project"
            )
        return row
    for project_value in (project_id, None):
        row = await db.scalar(
            select(ReportTemplateVersion)
            .join(ReportTemplate, ReportTemplate.id == ReportTemplateVersion.template_id)
            .where(
                ReportTemplateVersion.organization_id == organization_id,
                ReportTemplateVersion.status == TemplateVersionStatus.PUBLISHED,
                ReportTemplate.report_type_key == report_type_key,
                ReportTemplate.active.is_(True),
                ReportTemplate.is_default.is_(True),
                ReportTemplate.project_id == project_value
                if project_value is not None
                else ReportTemplate.project_id.is_(None),
            )
            .order_by(ReportTemplateVersion.version.desc())
            .limit(1)
        )
        if row:
            return row
    return await _ensure_builtin_default(
        db,
        organization_id=organization_id,
        report_type_key=report_type_key,
        actor_user_id=actor_user_id,
    )


async def build_report_payload(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    source_entity_id: UUID,
) -> dict[str, object]:
    provider = report_data_providers.get(report_type_key)
    return await provider.build_payload(db, organization_id, project_id, source_entity_id)


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return normalized or "report"


async def render_report_instance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    source_entity_id: UUID,
    actor_user_id: UUID,
    output_format: TemplateOutputFormat,
    template_version_id: UUID | None = None,
    persist_history: bool = True,
) -> tuple[bytes, str, str, ReportTemplateVersion, ReportRenderRecord | None]:
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
    validate_layout_against_contract(layout, provider.contract)
    content, content_type, extension = render_report(payload, layout, output_format)
    digest = hashlib.sha256(content).hexdigest()
    revision_value = resolve_path(payload, provider.contract.source_revision_path)
    try:
        source_revision = int(str(revision_value))
    except (TypeError, ValueError) as exc:
        raise ReportTemplateValidationError(
            f"Provider did not expose a valid source revision at {provider.contract.source_revision_path}"
        ) from exc
    record = None
    if persist_history:
        record = ReportRenderRecord(
            organization_id=organization_id,
            project_id=project_id,
            report_type_key=report_type_key,
            source_entity_type=provider.source_entity_type,
            source_entity_id=source_entity_id,
            source_revision=source_revision,
            template_version_id=template_version.id,
            output_format=output_format,
            payload_snapshot=payload,
            presentation_snapshot=layout.model_dump(mode="json"),
            content_sha256=digest,
            generated_by_user_id=actor_user_id,
        )
        db.add(record)
        await db.flush()
    report_number = resolve_path(payload, "report.number")
    base_name = _safe_filename(str(report_number or f"{report_type_key}-{source_entity_id}"))
    return content, content_type, f"{base_name}.{extension}", template_version, record


async def list_render_history(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_type_key: str,
    source_entity_id: UUID,
) -> list[ReportRenderRecord]:
    provider = report_data_providers.get(report_type_key)
    rows = await db.scalars(
        select(ReportRenderRecord)
        .where(
            ReportRenderRecord.organization_id == organization_id,
            ReportRenderRecord.project_id == project_id,
            ReportRenderRecord.report_type_key == report_type_key,
            ReportRenderRecord.source_entity_type == provider.source_entity_type,
            ReportRenderRecord.source_entity_id == source_entity_id,
        )
        .order_by(ReportRenderRecord.created_at.desc(), ReportRenderRecord.id.desc())
    )
    return list(rows.all())
