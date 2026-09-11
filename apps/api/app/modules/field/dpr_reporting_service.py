import hashlib
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.field.dpr_renderer import render_dpr
from app.modules.field.dpr_reporting_models import (
    DailyReportMaterialEntry,
    DPRBrandingProfile,
    DPROutputFormat,
    DPRRenderRecord,
    DPRSourceLink,
    DPRTemplate,
    DPRTemplateSourceKind,
    DPRTemplateVersion,
    DPRTemplateVersionStatus,
)
from app.modules.field.dpr_reporting_schemas import (
    DPRBrandingSpec,
    DPRBrandingUpdate,
    DPRCompanyNameMode,
    DPRHeaderFooterSpec,
    DPRLayoutElement,
    DPRLayoutElementKind,
    DPRLayoutSpec,
    DPRPageSpec,
    DPRTemplateCreate,
    DPRTemplateVersionCreate,
)
from app.modules.field.models import (
    DailyReport,
    DailyReportCrewEntry,
    DailyReportDelayEntry,
    DailyReportDeliveryEntry,
    DailyReportEquipmentEntry,
    DailyReportProductionEntry,
    DailyReportSafetyEntry,
    DailyReportWorkEntry,
)
from app.modules.files.models import FileAssetStatus, FileLink, FileVersion
from app.modules.organizations.models import Organization
from app.modules.projects.models import Project


class DPRReportingValidationError(ValueError):
    pass


class DPRReportingConflictError(ValueError):
    pass


SECTION_MODELS = {
    "crew": DailyReportCrewEntry,
    "work": DailyReportWorkEntry,
    "materials": DailyReportMaterialEntry,
    "equipment": DailyReportEquipmentEntry,
    "deliveries": DailyReportDeliveryEntry,
    "production": DailyReportProductionEntry,
    "delays": DailyReportDelayEntry,
    "safety": DailyReportSafetyEntry,
}


def default_dpr_layout() -> DPRLayoutSpec:
    elements = [
        DPRLayoutElement(id="project-summary", kind=DPRLayoutElementKind.PROJECT_SUMMARY, order=10, column_span=8, title="Project / DPR Details"),
        DPRLayoutElement(id="weather", kind=DPRLayoutElementKind.WEATHER, order=20, column_span=4, title="Weather"),
        DPRLayoutElement(id="work", kind=DPRLayoutElementKind.WORK, order=30, column_span=12, title="Work Progress"),
        DPRLayoutElement(id="crew", kind=DPRLayoutElementKind.CREW, order=40, column_span=12, title="Manpower / Crew"),
        DPRLayoutElement(id="materials", kind=DPRLayoutElementKind.MATERIALS, order=50, column_span=12, title="Material Consumption"),
        DPRLayoutElement(id="deliveries", kind=DPRLayoutElementKind.DELIVERIES, order=60, column_span=12, title="Material Received"),
        DPRLayoutElement(id="equipment", kind=DPRLayoutElementKind.EQUIPMENT, order=70, column_span=12, title="Plant & Equipment"),
        DPRLayoutElement(id="production", kind=DPRLayoutElementKind.PRODUCTION, order=80, column_span=12, title="Production / Quantity"),
        DPRLayoutElement(id="delays", kind=DPRLayoutElementKind.DELAYS, order=90, column_span=6, title="Delays / Constraints"),
        DPRLayoutElement(id="safety", kind=DPRLayoutElementKind.SAFETY, order=100, column_span=6, title="Safety"),
        DPRLayoutElement(id="photos", kind=DPRLayoutElementKind.PHOTOS, order=110, column_span=12, title="Site Photos"),
        DPRLayoutElement(id="notes", kind=DPRLayoutElementKind.NOTES, order=120, column_span=12, title="Remarks / Notes"),
        DPRLayoutElement(id="signatures", kind=DPRLayoutElementKind.SIGNATURES, order=130, column_span=12, title="Sign-off"),
    ]
    return DPRLayoutSpec(
        page=DPRPageSpec(),
        branding=DPRBrandingSpec(
            company_name_mode=DPRCompanyNameMode.ORGANIZATION,
            report_title="Daily Progress Report",
        ),
        header_footer=DPRHeaderFooterSpec(show_page_number=True),
        elements=elements,
    )


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return str(value)


def _model_row(row: object, fields: tuple[str, ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in fields:
        result[field] = _json_value(getattr(row, field, None))
    return result


async def _validate_file_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    asset_id: UUID,
    version: int,
) -> FileVersion:
    file_version = await db.scalar(
        select(FileVersion)
        .join(FileVersion.__table__.metadata.tables["file_assets"], FileVersion.asset_id == FileVersion.__table__.metadata.tables["file_assets"].c.id)
        .where(
            FileVersion.organization_id == organization_id,
            FileVersion.asset_id == asset_id,
            FileVersion.version == version,
            FileVersion.__table__.metadata.tables["file_assets"].c.status == FileAssetStatus.ACTIVE.value,
        )
    )
    if file_version is None:
        raise DPRReportingValidationError("File Asset version was not found or is not active")
    return file_version


async def get_branding_profile(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> DPRBrandingProfile | None:
    return await db.scalar(
        select(DPRBrandingProfile).where(DPRBrandingProfile.organization_id == organization_id)
    )


async def update_branding_profile(
    db: AsyncSession,
    *,
    organization_id: UUID,
    payload: DPRBrandingUpdate,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> DPRBrandingProfile:
    profile = await db.scalar(
        select(DPRBrandingProfile)
        .where(DPRBrandingProfile.organization_id == organization_id)
        .with_for_update()
    )
    if profile is None:
        if payload.expected_revision != 1:
            raise DPRReportingConflictError("DPR branding has not been created; expected_revision must be 1")
        profile = DPRBrandingProfile(
            organization_id=organization_id,
            revision=1,
            updated_by_user_id=actor_user_id,
        )
        db.add(profile)
        before: dict[str, object] | None = None
    else:
        if profile.revision != payload.expected_revision:
            raise DPRReportingConflictError(
                f"DPR branding changed from revision {payload.expected_revision} to {profile.revision}; refresh before saving"
            )
        before = {
            "display_name": profile.display_name,
            "logo_asset_id": str(profile.logo_asset_id) if profile.logo_asset_id else None,
            "logo_version": profile.logo_version,
            "header_text": profile.header_text,
            "footer_text": profile.footer_text,
            "revision": profile.revision,
        }
        profile.revision += 1

    if payload.logo_asset_id is not None and payload.logo_version is not None:
        await _validate_file_version(
            db,
            organization_id=organization_id,
            asset_id=payload.logo_asset_id,
            version=payload.logo_version,
        )
    profile.display_name = payload.display_name.strip() if payload.display_name else None
    profile.logo_asset_id = payload.logo_asset_id
    profile.logo_version = payload.logo_version
    profile.header_text = payload.header_text.strip() if payload.header_text else None
    profile.footer_text = payload.footer_text.strip() if payload.footer_text else None
    profile.updated_by_user_id = actor_user_id
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="dpr.branding.updated",
        target_type="dpr_branding_profile",
        target_id=str(profile.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "before": before,
            "after": {
                "display_name": profile.display_name,
                "logo_asset_id": str(profile.logo_asset_id) if profile.logo_asset_id else None,
                "logo_version": profile.logo_version,
                "header_text": profile.header_text,
                "footer_text": profile.footer_text,
                "revision": profile.revision,
            },
        },
    )
    return profile


async def list_templates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[DPRTemplate]:
    rows = await db.scalars(
        select(DPRTemplate)
        .where(
            DPRTemplate.organization_id == organization_id,
            DPRTemplate.active.is_(True),
            or_(DPRTemplate.project_id == project_id, DPRTemplate.project_id.is_(None)),
        )
        .order_by(DPRTemplate.project_id.desc().nullslast(), DPRTemplate.is_default.desc(), DPRTemplate.name)
    )
    return list(rows.all())


async def create_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    payload: DPRTemplateCreate,
    actor_user_id: UUID,
) -> DPRTemplate:
    target_project_id = None if payload.company_wide else project_id
    if payload.is_default:
        existing_defaults = await db.scalars(
            select(DPRTemplate).where(
                DPRTemplate.organization_id == organization_id,
                DPRTemplate.active.is_(True),
                DPRTemplate.is_default.is_(True),
                DPRTemplate.project_id.is_(None) if target_project_id is None else DPRTemplate.project_id == target_project_id,
            )
        )
        for row in existing_defaults.all():
            row.is_default = False
    template = DPRTemplate(
        organization_id=organization_id,
        project_id=target_project_id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        is_default=payload.is_default,
        created_by_user_id=actor_user_id,
    )
    db.add(template)
    await db.flush()
    return template


async def list_template_versions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    template_id: UUID,
) -> list[DPRTemplateVersion]:
    template = await _load_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        template_id=template_id,
    )
    rows = await db.scalars(
        select(DPRTemplateVersion)
        .where(
            DPRTemplateVersion.organization_id == organization_id,
            DPRTemplateVersion.template_id == template.id,
        )
        .order_by(DPRTemplateVersion.version.desc())
    )
    return list(rows.all())


async def _load_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    template_id: UUID,
    for_update: bool = False,
) -> DPRTemplate:
    query = select(DPRTemplate).where(
        DPRTemplate.id == template_id,
        DPRTemplate.organization_id == organization_id,
        DPRTemplate.active.is_(True),
        or_(DPRTemplate.project_id == project_id, DPRTemplate.project_id.is_(None)),
    )
    if for_update:
        query = query.with_for_update()
    template = await db.scalar(query)
    if template is None:
        raise DPRReportingValidationError("DPR template was not found for this project")
    return template


async def create_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    template_id: UUID,
    payload: DPRTemplateVersionCreate,
    actor_user_id: UUID,
) -> DPRTemplateVersion:
    template = await _load_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        template_id=template_id,
        for_update=True,
    )
    if payload.source_file_asset_id is not None and payload.source_file_version is not None:
        await _validate_file_version(
            db,
            organization_id=organization_id,
            asset_id=payload.source_file_asset_id,
            version=payload.source_file_version,
        )
    latest_version = await db.scalar(
        select(DPRTemplateVersion.version)
        .where(
            DPRTemplateVersion.organization_id == organization_id,
            DPRTemplateVersion.template_id == template.id,
        )
        .order_by(DPRTemplateVersion.version.desc())
        .limit(1)
    )
    version_number = int(latest_version or 0) + 1
    version = DPRTemplateVersion(
        organization_id=organization_id,
        template_id=template.id,
        version=version_number,
        status=DPRTemplateVersionStatus.DRAFT,
        source_kind=payload.source_kind,
        source_file_asset_id=payload.source_file_asset_id,
        source_file_version=payload.source_file_version,
        source_format=payload.source_format.strip().lower() if payload.source_format else None,
        layout_spec=payload.layout.model_dump(mode="json"),
        created_by_user_id=actor_user_id,
    )
    db.add(version)
    await db.flush()
    return version


async def publish_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    template_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> DPRTemplateVersion:
    template = await _load_template(
        db,
        organization_id=organization_id,
        project_id=project_id,
        template_id=template_id,
        for_update=True,
    )
    version = await db.scalar(
        select(DPRTemplateVersion)
        .where(
            DPRTemplateVersion.id == version_id,
            DPRTemplateVersion.organization_id == organization_id,
            DPRTemplateVersion.template_id == template.id,
        )
        .with_for_update()
    )
    if version is None or version.status != DPRTemplateVersionStatus.DRAFT:
        raise DPRReportingValidationError("Draft DPR template version was not found")
    DPRLayoutSpec.model_validate(version.layout_spec)
    published = await db.scalars(
        select(DPRTemplateVersion).where(
            DPRTemplateVersion.organization_id == organization_id,
            DPRTemplateVersion.template_id == template.id,
            DPRTemplateVersion.status == DPRTemplateVersionStatus.PUBLISHED,
        )
    )
    for row in published.all():
        row.status = DPRTemplateVersionStatus.RETIRED
    now = datetime.now(UTC)
    version.status = DPRTemplateVersionStatus.PUBLISHED
    version.published_by_user_id = actor_user_id
    version.published_at = now
    template.current_version = version.version
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="dpr.template.published",
        target_type="dpr_template_version",
        target_id=str(version.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "template_id": str(template.id),
            "version": version.version,
            "source_kind": version.source_kind.value,
            "source_file_asset_id": str(version.source_file_asset_id) if version.source_file_asset_id else None,
            "source_file_version": version.source_file_version,
        },
    )
    return version


async def _ensure_builtin_default_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
) -> DPRTemplateVersion:
    template = await db.scalar(
        select(DPRTemplate)
        .where(
            DPRTemplate.organization_id == organization_id,
            DPRTemplate.project_id.is_(None),
            DPRTemplate.is_default.is_(True),
            DPRTemplate.active.is_(True),
        )
        .order_by(DPRTemplate.created_at)
        .limit(1)
    )
    if template is None:
        template = DPRTemplate(
            organization_id=organization_id,
            project_id=None,
            name="India Standard DPR",
            description="Built-in India-first Daily Progress Report template.",
            active=True,
            is_default=True,
            current_version=0,
            created_by_user_id=actor_user_id,
        )
        db.add(template)
        await db.flush()
    if template.current_version:
        current = await db.scalar(
            select(DPRTemplateVersion).where(
                DPRTemplateVersion.organization_id == organization_id,
                DPRTemplateVersion.template_id == template.id,
                DPRTemplateVersion.version == template.current_version,
                DPRTemplateVersion.status == DPRTemplateVersionStatus.PUBLISHED,
            )
        )
        if current is not None:
            return current
    version = DPRTemplateVersion(
        organization_id=organization_id,
        template_id=template.id,
        version=1,
        status=DPRTemplateVersionStatus.PUBLISHED,
        source_kind=DPRTemplateSourceKind.BUILTIN,
        layout_spec=default_dpr_layout().model_dump(mode="json"),
        created_by_user_id=actor_user_id,
        published_by_user_id=actor_user_id,
        published_at=datetime.now(UTC),
    )
    db.add(version)
    template.current_version = 1
    await db.flush()
    return version


async def resolve_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    actor_user_id: UUID,
    explicit_version_id: UUID | None = None,
) -> DPRTemplateVersion:
    if explicit_version_id is not None:
        row = await db.scalar(
            select(DPRTemplateVersion)
            .join(DPRTemplate, DPRTemplate.id == DPRTemplateVersion.template_id)
            .where(
                DPRTemplateVersion.id == explicit_version_id,
                DPRTemplateVersion.organization_id == organization_id,
                DPRTemplateVersion.status == DPRTemplateVersionStatus.PUBLISHED,
                DPRTemplate.active.is_(True),
                or_(DPRTemplate.project_id == project_id, DPRTemplate.project_id.is_(None)),
            )
        )
        if row is None:
            raise DPRReportingValidationError("Published DPR template version is not available to this project")
        return row

    row = await db.scalar(
        select(DPRTemplateVersion)
        .join(DPRTemplate, DPRTemplate.id == DPRTemplateVersion.template_id)
        .where(
            DPRTemplateVersion.organization_id == organization_id,
            DPRTemplateVersion.status == DPRTemplateVersionStatus.PUBLISHED,
            DPRTemplate.active.is_(True),
            DPRTemplate.is_default.is_(True),
            DPRTemplate.project_id == project_id,
        )
        .order_by(DPRTemplateVersion.version.desc())
        .limit(1)
    )
    if row is not None:
        return row
    row = await db.scalar(
        select(DPRTemplateVersion)
        .join(DPRTemplate, DPRTemplate.id == DPRTemplateVersion.template_id)
        .where(
            DPRTemplateVersion.organization_id == organization_id,
            DPRTemplateVersion.status == DPRTemplateVersionStatus.PUBLISHED,
            DPRTemplate.active.is_(True),
            DPRTemplate.is_default.is_(True),
            DPRTemplate.project_id.is_(None),
        )
        .order_by(DPRTemplateVersion.version.desc())
        .limit(1)
    )
    if row is not None:
        return row
    return await _ensure_builtin_default_template(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )


async def _report_or_error(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> DailyReport:
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        raise DPRReportingValidationError("Daily Progress Report was not found")
    return report


async def build_dpr_snapshot(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> dict[str, object]:
    report = await _report_or_error(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    organization = await db.get(Organization, organization_id)
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if organization is None or project is None:
        raise DPRReportingValidationError("DPR organization or project was not found")

    section_fields: dict[str, tuple[str, ...]] = {
        "crew": ("id", "company_name", "trade", "worker_count", "regular_hours", "overtime_hours", "notes"),
        "work": ("id", "description", "location", "cost_code", "quantity", "unit_code", "notes"),
        "materials": ("id", "material_id", "material_name", "quantity", "unit_code", "wbs_code_id", "boq_item_id", "location", "notes"),
        "equipment": ("id", "equipment_name", "equipment_reference", "hours_operated", "status", "notes"),
        "deliveries": ("id", "supplier", "material", "quantity", "unit_code", "delivered_at", "ticket_number", "notes"),
        "production": ("id", "description", "cost_code", "quantity", "unit_code", "location", "notes"),
        "delays": ("id", "category", "description", "started_at", "ended_at", "lost_hours", "responsible_party", "schedule_impact", "notes"),
        "safety": ("id", "entry_type", "summary", "severity", "safety_record_id", "notes"),
    }
    sections: dict[str, object] = {}
    entry_source_by_id: dict[str, dict[str, object]] = {}
    source_rows = await db.scalars(
        select(DPRSourceLink).where(
            DPRSourceLink.organization_id == organization_id,
            DPRSourceLink.daily_report_id == report.id,
        )
    )
    for link in source_rows.all():
        entry_source_by_id[str(link.entry_id)] = {
            "source_type": link.source_type,
            "source_id": link.source_id,
            "source_revision": link.source_revision,
        }

    for section_name, model in SECTION_MODELS.items():
        rows = await db.scalars(
            select(model)
            .where(
                model.organization_id == organization_id,
                model.daily_report_id == report.id,
            )
            .order_by(model.created_at, model.id)
        )
        values: list[dict[str, object]] = []
        for row in rows.all():
            item = _model_row(row, section_fields[section_name])
            source = entry_source_by_id.get(str(row.id))
            if source:
                item["source"] = source
            values.append(item)
        sections[section_name] = values

    photo_links = await db.scalars(
        select(FileLink)
        .where(
            FileLink.organization_id == organization_id,
            FileLink.entity_type == "daily_report",
            FileLink.entity_id == report.id,
            FileLink.relation_type.in_(("photo", "attachment")),
        )
        .order_by(FileLink.created_at, FileLink.id)
    )
    sections["photos"] = [
        {
            "asset_id": str(link.asset_id),
            "pinned_version": link.pinned_version,
            "relation_type": link.relation_type,
        }
        for link in photo_links.all()
    ]

    address_parts = [
        project.address_line_1,
        project.address_line_2,
        project.locality,
        project.region,
        project.postal_code,
        project.country_code,
    ]
    return {
        "schema_version": 1,
        "organization": {
            "id": str(organization.id),
            "name": organization.name,
            "legal_name": organization.legal_name,
        },
        "project": {
            "id": str(project.id),
            "number": project.number,
            "name": project.name,
            "address": ", ".join(part for part in address_parts if part),
            "timezone": project.timezone,
            "currency_code": project.currency_code,
        },
        "report": {
            "id": str(report.id),
            "report_date": report.report_date.isoformat(),
            "shift_code": report.shift_code,
            "status": report.status.value,
            "revision": report.revision,
            "weather_condition": report.weather_condition,
            "temperature_low": _json_value(report.temperature_low),
            "temperature_high": _json_value(report.temperature_high),
            "temperature_unit": report.temperature_unit,
            "notes": report.notes,
            "submitted_at": _json_value(report.submitted_at),
            "approved_at": _json_value(report.approved_at),
        },
        "sections": sections,
        "captured_at": datetime.now(UTC).isoformat(),
    }


async def prepare_dpr_render(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    actor_user_id: UUID,
    output_format: DPROutputFormat,
    template_version_id: UUID | None = None,
    record_generation: bool = True,
) -> tuple[bytes, str, str, DPRTemplateVersion, DPRRenderRecord | None, dict[str, object]]:
    snapshot = await build_dpr_snapshot(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    template_version = await resolve_template_version(
        db,
        organization_id=organization_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        explicit_version_id=template_version_id,
    )
    layout = DPRLayoutSpec.model_validate(template_version.layout_spec)
    branding = await get_branding_profile(db, organization_id=organization_id)
    if branding is not None:
        layout_data = layout.model_dump(mode="json")
        if layout.branding.company_name_mode == DPRCompanyNameMode.ORGANIZATION and branding.display_name:
            layout_data["branding"]["company_name_mode"] = "custom"
            layout_data["branding"]["custom_company_name"] = branding.display_name
        if branding.logo_asset_id and branding.logo_version:
            layout_data["branding"]["logo_asset_id"] = str(branding.logo_asset_id)
            layout_data["branding"]["logo_version"] = branding.logo_version
        if branding.header_text and not any(
            (
                layout.header_footer.header_left,
                layout.header_footer.header_center,
                layout.header_footer.header_right,
            )
        ):
            layout_data["header_footer"]["header_center"] = branding.header_text
        if branding.footer_text and not any(
            (
                layout.header_footer.footer_left,
                layout.header_footer.footer_center,
                layout.header_footer.footer_right,
            )
        ):
            layout_data["header_footer"]["footer_center"] = branding.footer_text
        layout = DPRLayoutSpec.model_validate(layout_data)

    content, content_type, extension = render_dpr(snapshot, layout, output_format)
    digest = hashlib.sha256(content).hexdigest()
    record: DPRRenderRecord | None = None
    if record_generation:
        report_revision = int(snapshot["report"]["revision"])  # type: ignore[index]
        record = DPRRenderRecord(
            organization_id=organization_id,
            project_id=project_id,
            daily_report_id=report_id,
            report_revision=report_revision,
            template_version_id=template_version.id,
            output_format=output_format,
            data_snapshot=snapshot,
            presentation_snapshot=layout.model_dump(mode="json"),
            content_sha256=digest,
            generated_by_user_id=actor_user_id,
        )
        db.add(record)
        await db.flush()
    return content, content_type, extension, template_version, record, {
        "data_snapshot": snapshot,
        "presentation_snapshot": layout.model_dump(mode="json"),
        "content_sha256": digest,
    }


async def list_render_history(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> list[DPRRenderRecord]:
    await _report_or_error(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    rows = await db.scalars(
        select(DPRRenderRecord)
        .where(
            DPRRenderRecord.organization_id == organization_id,
            DPRRenderRecord.project_id == project_id,
            DPRRenderRecord.daily_report_id == report_id,
        )
        .order_by(DPRRenderRecord.created_at.desc(), DPRRenderRecord.id.desc())
    )
    return list(rows.all())
