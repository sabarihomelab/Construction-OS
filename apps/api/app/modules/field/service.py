from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.configuration.schemas import EffectiveConfigurationRead
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.events.service import enqueue_event
from app.modules.field.models import (
    DailyReport,
    DailyReportCrewEntry,
    DailyReportDelayEntry,
    DailyReportDeliveryEntry,
    DailyReportEquipmentEntry,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportProductionEntry,
    DailyReportSafetyEntry,
    DailyReportStatus,
    DailyReportWorkEntry,
)
from app.modules.files.models import FileLink
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.search.service import schedule_search_index


class DailyReportValidationError(ValueError):
    pass


class DailyReportConflictError(ValueError):
    pass


SECTION_MODELS = {
    "crew": DailyReportCrewEntry,
    "work": DailyReportWorkEntry,
    "equipment": DailyReportEquipmentEntry,
    "deliveries": DailyReportDeliveryEntry,
    "production": DailyReportProductionEntry,
    "delays": DailyReportDelayEntry,
    "safety": DailyReportSafetyEntry,
}


def _setting(config: EffectiveConfigurationRead, key: str, default: object) -> object:
    for setting in config.settings:
        if setting.key == key:
            return setting.value
    return default


def _string_list(value: object, *, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DailyReportValidationError(f"Configuration {key} must be a list of section names")
    return list(dict.fromkeys(value))


def _report_summary(report: DailyReport) -> dict[str, object]:
    return {
        "project_id": str(report.project_id),
        "report_date": report.report_date,
        "shift_code": report.shift_code,
        "status": report.status.value,
        "revision": report.revision,
    }


async def _history(
    db: AsyncSession,
    *,
    report: DailyReport,
    event_type: DailyReportHistoryType,
    actor_user_id: UUID,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        DailyReportHistoryEvent(
            organization_id=report.organization_id,
            daily_report_id=report.id,
            event_type=event_type,
            report_revision=report.revision,
            actor_user_id=actor_user_id,
            details=details or {},
        )
    )


async def _publish_change(
    db: AsyncSession,
    *,
    report: DailyReport,
    event_type: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=report.organization_id,
        event_type=event_type,
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
        required_permission_key="field.daily_report.view",
        scope_type="project",
        scope_id=report.project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": report.revision, "status": report.status.value},
    )
    await schedule_search_index(
        db,
        organization_id=report.organization_id,
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
    )


async def _load_report_for_update(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
) -> DailyReport:
    report = await db.scalar(
        select(DailyReport)
        .where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
        .with_for_update()
    )
    if report is None:
        raise DailyReportValidationError("Daily Report was not found")
    if report.revision != expected_revision:
        raise DailyReportConflictError(
            f"Daily Report changed from revision {expected_revision} to {report.revision}; refresh before saving"
        )
    return report


async def _require_active_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    project_membership = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if project_membership is None:
        raise DailyReportValidationError("An active project membership is required")


async def create_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> DailyReport:
    project = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise DailyReportValidationError("Project was not found")
    await _require_active_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )

    data = dict(values)
    shift_code = str(data.get("shift_code") or "day").strip().lower()
    if not shift_code:
        raise DailyReportValidationError("Shift code is required")
    data["shift_code"] = shift_code

    existing = await db.scalar(
        select(DailyReport.id).where(
            DailyReport.project_id == project_id,
            DailyReport.report_date == data.get("report_date"),
            DailyReport.shift_code == shift_code,
        )
    )
    if existing is not None:
        raise DailyReportConflictError("A Daily Report already exists for this project, date and shift")

    report = DailyReport(
        organization_id=organization_id,
        project_id=project_id,
        prepared_by_membership_id=membership_id,
        created_by_user_id=actor_user_id,
        **data,
    )
    db.add(report)
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.CREATED,
        actor_user_id=actor_user_id,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.created",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"after": _report_summary(report)},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.created",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def update_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status != DailyReportStatus.DRAFT:
        raise DailyReportValidationError("Only a draft Daily Report can be edited")

    before = _report_summary(report)
    mutable = {
        "shift_code",
        "weather_condition",
        "temperature_low",
        "temperature_high",
        "temperature_unit",
        "notes",
    }
    for key, value in changes.items():
        if key not in mutable:
            continue
        if key == "shift_code" and isinstance(value, str):
            value = value.strip().lower()
            if not value:
                raise DailyReportValidationError("Shift code is required")
        setattr(report, key, value)

    if (
        report.temperature_low is not None
        and report.temperature_high is not None
        and report.temperature_low > report.temperature_high
    ):
        raise DailyReportValidationError("Low temperature cannot exceed high temperature")

    report.revision += 1
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.UPDATED,
        actor_user_id=actor_user_id,
        details={"reason": reason} if reason else {},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.updated",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": before, "after": _report_summary(report)},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.updated",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def replace_daily_report_sections(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    report_id: UUID,
    expected_revision: int,
    sections: Mapping[str, list[Mapping[str, object]] | None],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status != DailyReportStatus.DRAFT:
        raise DailyReportValidationError("Only a draft Daily Report can be edited")

    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="field",
        project_id=project_id,
    )
    enabled = set(
        _string_list(
            _setting(config, "field.daily_reports.sections.enabled", ["crew", "work", "photos", "notes"]),
            key="field.daily_reports.sections.enabled",
        )
    )

    changed_sections: list[str] = []
    for section_name, entries in sections.items():
        if entries is None:
            continue
        if section_name not in SECTION_MODELS:
            continue
        if section_name not in enabled:
            raise DailyReportValidationError(f"Section is disabled by project configuration: {section_name}")
        model = SECTION_MODELS[section_name]
        await db.execute(
            delete(model).where(
                model.daily_report_id == report.id,
                model.organization_id == organization_id,
            )
        )
        for values in entries:
            db.add(model(organization_id=organization_id, daily_report_id=report.id, **dict(values)))
        changed_sections.append(section_name)

    if not changed_sections:
        return report

    report.revision += 1
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.UPDATED,
        actor_user_id=actor_user_id,
        details={"sections": sorted(changed_sections), "reason": reason},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.sections.updated",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"sections": sorted(changed_sections), "revision": report.revision},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.updated",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def _section_has_content(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
    section_name: str,
) -> bool:
    if section_name == "weather":
        return any(
            value is not None and value != ""
            for value in (
                report.weather_condition,
                report.temperature_low,
                report.temperature_high,
            )
        )
    if section_name == "notes":
        return bool(report.notes and report.notes.strip())
    if section_name == "photos":
        count = await db.scalar(
            select(func.count(FileLink.id)).where(
                FileLink.organization_id == organization_id,
                FileLink.entity_type == "daily_report",
                FileLink.entity_id == report.id,
                FileLink.relation_type.in_(("photo", "attachment")),
            )
        )
        return bool(count)
    model = SECTION_MODELS.get(section_name)
    if model is None:
        return False
    count = await db.scalar(
        select(func.count(model.id)).where(
            model.organization_id == organization_id,
            model.daily_report_id == report.id,
        )
    )
    return bool(count)


async def submit_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    report_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status != DailyReportStatus.DRAFT:
        raise DailyReportValidationError("Only a draft Daily Report can be submitted")

    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="field",
        project_id=project_id,
    )
    enabled = _string_list(
        _setting(config, "field.daily_reports.sections.enabled", ["crew", "work", "photos", "notes"]),
        key="field.daily_reports.sections.enabled",
    )
    required = _string_list(
        _setting(config, "field.daily_reports.sections.required", ["work"]),
        key="field.daily_reports.sections.required",
    )
    invalid_required = sorted(set(required) - set(enabled))
    if invalid_required:
        raise DailyReportValidationError(
            "Required Daily Report sections are disabled: " + ", ".join(invalid_required)
        )

    missing = [
        section
        for section in required
        if not await _section_has_content(
            db,
            organization_id=organization_id,
            report=report,
            section_name=section,
        )
    ]
    if missing:
        raise DailyReportValidationError(
            "Complete the required Daily Report sections before submitting: " + ", ".join(missing)
        )

    approval_required = bool(
        _setting(config, "field.daily_reports.approval.required", False)
    )
    now = datetime.now(UTC)
    report.submitted_at = now
    report.configuration_context = {
        "configuration_revisions": config.configuration_revisions,
        "preference_revision": config.preference_revision,
        "project_template_version_id": (
            str(config.project_template_version_id) if config.project_template_version_id else None
        ),
        "enabled_sections": enabled,
        "required_sections": required,
        "approval_required": approval_required,
        "effective_at": now.isoformat(),
    }
    report.status = DailyReportStatus.IN_REVIEW if approval_required else DailyReportStatus.APPROVED
    if not approval_required:
        report.approved_at = now
    report.revision += 1
    await db.flush()

    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.SUBMITTED,
        actor_user_id=actor_user_id,
        details={"approval_required": approval_required},
    )
    if not approval_required:
        await _history(
            db,
            report=report,
            event_type=DailyReportHistoryType.APPROVED,
            actor_user_id=actor_user_id,
            details={"approval_not_required": True},
        )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.submitted",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "status": report.status.value,
            "revision": report.revision,
            "approval_required": approval_required,
        },
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.submitted",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def approve_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status != DailyReportStatus.IN_REVIEW:
        raise DailyReportValidationError("Only a Daily Report in review can be approved")
    report.status = DailyReportStatus.APPROVED
    report.approved_at = datetime.now(UTC)
    report.rejected_at = None
    report.revision += 1
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.APPROVED,
        actor_user_id=actor_user_id,
        details={"reason": reason} if reason else {},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.approved",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": report.status.value, "revision": report.revision},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.approved",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def reject_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    reason: str,
    session_id: UUID | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status != DailyReportStatus.IN_REVIEW:
        raise DailyReportValidationError("Only a Daily Report in review can be rejected")
    if not reason.strip():
        raise DailyReportValidationError("A rejection reason is required")
    report.status = DailyReportStatus.REJECTED
    report.rejected_at = datetime.now(UTC)
    report.approved_at = None
    report.revision += 1
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.REJECTED,
        actor_user_id=actor_user_id,
        details={"reason": reason.strip()},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.rejected",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason.strip(),
        changes={"status": report.status.value, "revision": report.revision},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.rejected",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def reopen_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status != DailyReportStatus.REJECTED:
        raise DailyReportValidationError("Only a rejected Daily Report can be reopened")
    report.status = DailyReportStatus.DRAFT
    report.rejected_at = None
    report.configuration_context = {}
    report.revision += 1
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.REOPENED,
        actor_user_id=actor_user_id,
        details={"reason": reason} if reason else {},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.reopened",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report


async def void_daily_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    reason: str,
    session_id: UUID | None = None,
) -> DailyReport:
    report = await _load_report_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    if report.status == DailyReportStatus.VOID:
        return report
    if not reason.strip():
        raise DailyReportValidationError("A reason is required to void a Daily Report")
    report.status = DailyReportStatus.VOID
    report.voided_at = datetime.now(UTC)
    report.revision += 1
    await db.flush()
    await _history(
        db,
        report=report,
        event_type=DailyReportHistoryType.VOIDED,
        actor_user_id=actor_user_id,
        details={"reason": reason.strip()},
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.voided",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason.strip(),
        changes={"status": report.status.value, "revision": report.revision},
    )
    await _publish_change(
        db,
        report=report,
        event_type="daily_report.voided",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return report
