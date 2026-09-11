from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import Party
from app.modules.equipment.consumption_models import (
    MaterialConsumption,
    MaterialConsumptionStatus,
)
from app.modules.equipment.models import (
    EquipmentAsset,
    Material,
    MaterialDelivery,
    MaterialDeliveryStatus,
    ProjectEquipmentAssignment,
)
from app.modules.equipment.usage_models import EquipmentUsage, EquipmentUsageStatus
from app.modules.events.service import enqueue_event
from app.modules.field.dpr_reporting_models import DailyReportMaterialEntry, DPRSourceLink
from app.modules.field.models import (
    DailyReport,
    DailyReportCrewEntry,
    DailyReportDeliveryEntry,
    DailyReportEquipmentEntry,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportStatus,
)
from app.modules.organizations.models import OrganizationSettings
from app.modules.search.service import schedule_search_index
from app.modules.workforce.attendance_models import (
    AttendanceEntry,
    AttendanceMarkStatus,
    AttendanceRegister,
    AttendanceRegisterStatus,
)


class DPRSourceSyncValidationError(ValueError):
    pass


class DPRSourceSyncConflictError(ValueError):
    pass


_SOURCE_SECTION_MODELS = {
    "attendance": ("crew", DailyReportCrewEntry),
    "materials": ("materials", DailyReportMaterialEntry),
    "equipment": ("equipment", DailyReportEquipmentEntry),
    "deliveries": ("deliveries", DailyReportDeliveryEntry),
}


async def _load_report_for_sync(
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
        raise DPRSourceSyncValidationError("Daily Progress Report was not found")
    if report.revision != expected_revision:
        raise DPRSourceSyncConflictError(
            f"DPR changed from revision {expected_revision} to {report.revision}; refresh before pulling source data"
        )
    if report.status != DailyReportStatus.DRAFT:
        raise DPRSourceSyncValidationError("Authoritative source data can only be refreshed on a draft DPR")
    return report


async def _remove_imported_rows(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report_id: UUID,
    source_type: str,
) -> None:
    section_name, model = _SOURCE_SECTION_MODELS[source_type]
    links = list(
        (
            await db.scalars(
                select(DPRSourceLink).where(
                    DPRSourceLink.organization_id == organization_id,
                    DPRSourceLink.daily_report_id == report_id,
                    DPRSourceLink.section_name == section_name,
                    DPRSourceLink.source_type == source_type,
                )
            )
        ).all()
    )
    if links:
        ids = [link.entry_id for link in links]
        await db.execute(
            delete(model).where(
                model.organization_id == organization_id,
                model.daily_report_id == report_id,
                model.id.in_(ids),
            )
        )
        await db.execute(
            delete(DPRSourceLink).where(
                DPRSourceLink.organization_id == organization_id,
                DPRSourceLink.daily_report_id == report_id,
                DPRSourceLink.section_name == section_name,
                DPRSourceLink.source_type == source_type,
            )
        )


async def _sync_attendance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> int:
    await _remove_imported_rows(
        db,
        organization_id=organization_id,
        report_id=report.id,
        source_type="attendance",
    )
    register = await db.scalar(
        select(AttendanceRegister).where(
            AttendanceRegister.organization_id == organization_id,
            AttendanceRegister.project_id == report.project_id,
            AttendanceRegister.attendance_date == report.report_date,
            AttendanceRegister.shift_code == report.shift_code,
            AttendanceRegister.status == AttendanceRegisterStatus.APPROVED,
        )
    )
    if register is None:
        return 0
    entries = list(
        (
            await db.scalars(
                select(AttendanceEntry)
                .where(
                    AttendanceEntry.organization_id == organization_id,
                    AttendanceEntry.project_id == report.project_id,
                    AttendanceEntry.register_id == register.id,
                )
                .order_by(AttendanceEntry.created_at, AttendanceEntry.id)
            )
        ).all()
    )
    party_ids = {entry.employer_party_id for entry in entries if entry.employer_party_id is not None}
    party_names: dict[UUID, str] = {}
    if party_ids:
        parties = await db.scalars(
            select(Party).where(
                Party.organization_id == organization_id,
                Party.id.in_(party_ids),
            )
        )
        party_names = {row.id: row.name for row in parties.all()}

    groups: dict[tuple[UUID | None, UUID | None, str | None], dict[str, object]] = defaultdict(
        lambda: {
            "worker_count": 0,
            "absent_count": 0,
            "regular_hours": Decimal(0),
            "overtime_hours": Decimal(0),
        }
    )
    working_marks = {AttendanceMarkStatus.PRESENT, AttendanceMarkStatus.HALF_DAY}
    for entry in entries:
        key = (entry.employer_party_id, entry.crew_id, entry.trade)
        group = groups[key]
        if entry.mark_status in working_marks:
            group["worker_count"] = int(group["worker_count"]) + 1
        if entry.mark_status == AttendanceMarkStatus.ABSENT:
            group["absent_count"] = int(group["absent_count"]) + 1
        group["regular_hours"] = Decimal(group["regular_hours"]) + entry.regular_hours
        group["overtime_hours"] = Decimal(group["overtime_hours"]) + entry.overtime_hours

    for (employer_id, crew_id, trade), group in groups.items():
        company_name = party_names.get(employer_id) if employer_id else None
        absent_count = int(group["absent_count"])
        notes = f"Imported from approved attendance {register.attendance_date.isoformat()} / {register.shift_code}."
        if absent_count:
            notes += f" {absent_count} absent."
        row = DailyReportCrewEntry(
            organization_id=organization_id,
            daily_report_id=report.id,
            company_name=company_name,
            trade=trade,
            worker_count=int(group["worker_count"]),
            regular_hours=Decimal(group["regular_hours"]),
            overtime_hours=Decimal(group["overtime_hours"]),
            notes=notes,
        )
        db.add(row)
        await db.flush()
        source_key = ":".join(
            [
                str(register.id),
                str(employer_id or "none"),
                str(crew_id or "none"),
                trade or "none",
            ]
        )
        db.add(
            DPRSourceLink(
                organization_id=organization_id,
                daily_report_id=report.id,
                section_name="crew",
                entry_type="daily_report_crew_entry",
                entry_id=row.id,
                source_type="attendance",
                source_id=source_key,
                source_revision=register.revision,
                source_snapshot={
                    "attendance_register_id": str(register.id),
                    "employer_party_id": str(employer_id) if employer_id else None,
                    "crew_id": str(crew_id) if crew_id else None,
                    "trade": trade,
                    "worker_count": int(group["worker_count"]),
                    "absent_count": absent_count,
                    "regular_hours": format(Decimal(group["regular_hours"]), "f"),
                    "overtime_hours": format(Decimal(group["overtime_hours"]), "f"),
                },
            )
        )
    return len(groups)


async def _sync_materials(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> int:
    await _remove_imported_rows(
        db,
        organization_id=organization_id,
        report_id=report.id,
        source_type="materials",
    )
    records = list(
        (
            await db.scalars(
                select(MaterialConsumption)
                .where(
                    MaterialConsumption.organization_id == organization_id,
                    MaterialConsumption.project_id == report.project_id,
                    MaterialConsumption.consumption_date == report.report_date,
                    MaterialConsumption.status == MaterialConsumptionStatus.POSTED,
                )
                .order_by(MaterialConsumption.created_at, MaterialConsumption.id)
            )
        ).all()
    )
    material_ids = {row.material_id for row in records}
    materials = await db.scalars(
        select(Material).where(
            Material.organization_id == organization_id,
            Material.id.in_(material_ids),
        )
    ) if material_ids else None
    material_names = {row.id: row.name for row in materials.all()} if materials is not None else {}
    for source in records:
        row = DailyReportMaterialEntry(
            organization_id=organization_id,
            project_id=report.project_id,
            daily_report_id=report.id,
            material_id=source.material_id,
            material_name=material_names.get(source.material_id, str(source.material_id)),
            quantity=source.quantity,
            unit_code=source.unit_code,
            wbs_code_id=source.wbs_code_id,
            boq_item_id=source.boq_item_id,
            location=source.location,
            notes=source.notes,
        )
        db.add(row)
        await db.flush()
        db.add(
            DPRSourceLink(
                organization_id=organization_id,
                daily_report_id=report.id,
                section_name="materials",
                entry_type="daily_report_material_entry",
                entry_id=row.id,
                source_type="materials",
                source_id=str(source.id),
                source_revision=source.revision,
                source_snapshot={
                    "material_consumption_id": str(source.id),
                    "material_id": str(source.material_id),
                    "quantity": format(source.quantity, "f"),
                    "unit_code": source.unit_code,
                    "wbs_code_id": str(source.wbs_code_id) if source.wbs_code_id else None,
                    "boq_item_id": str(source.boq_item_id) if source.boq_item_id else None,
                },
            )
        )
    return len(records)


async def _sync_equipment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> int:
    await _remove_imported_rows(
        db,
        organization_id=organization_id,
        report_id=report.id,
        source_type="equipment",
    )
    usages = list(
        (
            await db.scalars(
                select(EquipmentUsage)
                .where(
                    EquipmentUsage.organization_id == organization_id,
                    EquipmentUsage.project_id == report.project_id,
                    EquipmentUsage.usage_date == report.report_date,
                    EquipmentUsage.shift_code == report.shift_code,
                    EquipmentUsage.status == EquipmentUsageStatus.POSTED,
                )
                .order_by(EquipmentUsage.created_at, EquipmentUsage.id)
            )
        ).all()
    )
    assignment_ids = {row.equipment_assignment_id for row in usages}
    assignments = await db.scalars(
        select(ProjectEquipmentAssignment).where(
            ProjectEquipmentAssignment.organization_id == organization_id,
            ProjectEquipmentAssignment.project_id == report.project_id,
            ProjectEquipmentAssignment.id.in_(assignment_ids),
        )
    ) if assignment_ids else None
    assignment_by_id = {row.id: row for row in assignments.all()} if assignments is not None else {}
    asset_ids = {row.equipment_asset_id for row in assignment_by_id.values()}
    assets = await db.scalars(
        select(EquipmentAsset).where(
            EquipmentAsset.organization_id == organization_id,
            EquipmentAsset.id.in_(asset_ids),
        )
    ) if asset_ids else None
    asset_by_id = {row.id: row for row in assets.all()} if assets is not None else {}

    for source in usages:
        assignment = assignment_by_id.get(source.equipment_assignment_id)
        asset = asset_by_id.get(assignment.equipment_asset_id) if assignment else None
        row = DailyReportEquipmentEntry(
            organization_id=organization_id,
            daily_report_id=report.id,
            equipment_name=asset.name if asset else f"Equipment {source.equipment_assignment_id}",
            equipment_reference=asset.asset_number if asset else str(source.equipment_assignment_id),
            hours_operated=source.operating_hours or Decimal(0),
            status="posted",
            notes=source.notes,
        )
        db.add(row)
        await db.flush()
        db.add(
            DPRSourceLink(
                organization_id=organization_id,
                daily_report_id=report.id,
                section_name="equipment",
                entry_type="daily_report_equipment_entry",
                entry_id=row.id,
                source_type="equipment",
                source_id=str(source.id),
                source_revision=source.revision,
                source_snapshot={
                    "equipment_usage_id": str(source.id),
                    "equipment_assignment_id": str(source.equipment_assignment_id),
                    "asset_id": str(asset.id) if asset else None,
                    "operating_hours": format(source.operating_hours or Decimal(0), "f"),
                    "wbs_code_id": str(source.wbs_code_id) if source.wbs_code_id else None,
                    "boq_item_id": str(source.boq_item_id) if source.boq_item_id else None,
                },
            )
        )
    return len(usages)


async def _project_day_utc_bounds(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_timezone: str | None,
    report_date,
) -> tuple[datetime, datetime]:
    timezone_name = project_timezone
    if not timezone_name:
        settings = await db.get(OrganizationSettings, organization_id)
        timezone_name = settings.timezone if settings is not None else "Asia/Kolkata"
    try:
        zone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise DPRSourceSyncValidationError(f"Invalid project timezone: {timezone_name}") from exc
    local_start = datetime.combine(report_date, time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


async def _sync_deliveries(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
    project_timezone: str | None,
) -> int:
    await _remove_imported_rows(
        db,
        organization_id=organization_id,
        report_id=report.id,
        source_type="deliveries",
    )
    start_utc, end_utc = await _project_day_utc_bounds(
        db,
        organization_id=organization_id,
        project_timezone=project_timezone,
        report_date=report.report_date,
    )
    records = list(
        (
            await db.scalars(
                select(MaterialDelivery)
                .where(
                    MaterialDelivery.organization_id == organization_id,
                    MaterialDelivery.project_id == report.project_id,
                    MaterialDelivery.status == MaterialDeliveryStatus.RECEIVED,
                    MaterialDelivery.delivered_at >= start_utc,
                    MaterialDelivery.delivered_at < end_utc,
                )
                .order_by(MaterialDelivery.delivered_at, MaterialDelivery.id)
            )
        ).all()
    )
    material_ids = {row.material_id for row in records}
    materials = await db.scalars(
        select(Material).where(
            Material.organization_id == organization_id,
            Material.id.in_(material_ids),
        )
    ) if material_ids else None
    material_names = {row.id: row.name for row in materials.all()} if materials is not None else {}
    for source in records:
        row = DailyReportDeliveryEntry(
            organization_id=organization_id,
            daily_report_id=report.id,
            supplier=source.supplier,
            material=material_names.get(source.material_id, str(source.material_id)),
            quantity=source.quantity,
            unit_code=source.unit_code,
            delivered_at=source.delivered_at,
            ticket_number=source.ticket_number,
            notes=source.notes,
        )
        db.add(row)
        await db.flush()
        db.add(
            DPRSourceLink(
                organization_id=organization_id,
                daily_report_id=report.id,
                section_name="deliveries",
                entry_type="daily_report_delivery_entry",
                entry_id=row.id,
                source_type="deliveries",
                source_id=str(source.id),
                source_revision=source.revision,
                source_snapshot={
                    "material_delivery_id": str(source.id),
                    "material_id": str(source.material_id),
                    "quantity": format(source.quantity, "f"),
                    "unit_code": source.unit_code,
                    "delivered_at": source.delivered_at.isoformat(),
                },
            )
        )
    return len(records)


async def sync_dpr_sources(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    project_timezone: str | None,
    report_id: UUID,
    expected_revision: int,
    sources: list[str],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> tuple[DailyReport, dict[str, int]]:
    supported = set(_SOURCE_SECTION_MODELS)
    requested = list(dict.fromkeys(sources))
    unknown = sorted(set(requested) - supported)
    if unknown:
        raise DPRSourceSyncValidationError("Unsupported DPR source: " + ", ".join(unknown))
    if not requested:
        raise DPRSourceSyncValidationError("Select at least one DPR source to refresh")
    report = await _load_report_for_sync(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
        expected_revision=expected_revision,
    )
    counts: dict[str, int] = {}
    for source in requested:
        if source == "attendance":
            counts[source] = await _sync_attendance(
                db,
                organization_id=organization_id,
                report=report,
            )
        elif source == "materials":
            counts[source] = await _sync_materials(
                db,
                organization_id=organization_id,
                report=report,
            )
        elif source == "equipment":
            counts[source] = await _sync_equipment(
                db,
                organization_id=organization_id,
                report=report,
            )
        elif source == "deliveries":
            counts[source] = await _sync_deliveries(
                db,
                organization_id=organization_id,
                report=report,
                project_timezone=project_timezone,
            )

    report.revision += 1
    await db.flush()
    db.add(
        DailyReportHistoryEvent(
            organization_id=organization_id,
            daily_report_id=report.id,
            event_type=DailyReportHistoryType.UPDATED,
            report_revision=report.revision,
            actor_user_id=actor_user_id,
            details={"source_sync": counts, "sources": requested},
        )
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="daily_report.sources.refreshed",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"sources": requested, "imported_rows": counts, "revision": report.revision},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="daily_report.sources.refreshed",
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
        required_permission_key="field.daily_report.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": report.revision, "source_counts": counts},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
    )
    return report, counts
