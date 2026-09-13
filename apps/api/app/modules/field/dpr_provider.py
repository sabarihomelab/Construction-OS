from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import (
    BOQItem,
    Party,
    ProjectPartyAssignment,
    ProjectPartyRole,
    WBSCode,
)
from app.modules.equipment.consumption_models import (
    MaterialConsumption,
    MaterialConsumptionStatus,
)
from app.modules.equipment.models import EquipmentAsset, Material, ProjectEquipmentAssignment
from app.modules.equipment.usage_models import EquipmentUsage, EquipmentUsageStatus
from app.modules.field.dpr_models import DPRWorkProgressEntry
from app.modules.field.models import (
    DailyReport,
    DailyReportDelayEntry,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportSafetyEntry,
    DailyReportWorkEntry,
)
from app.modules.files.models import FileLink
from app.modules.identity.models import OrganizationMembership, User
from app.modules.metadata.models import CustomFieldDefinition, CustomFieldValue
from app.modules.organizations.models import Organization, OrganizationSettings
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.modules.projects.models import Project
from app.modules.reporting.template_models import ReportBrandingProfile
from app.modules.reporting.template_provider import (
    CollectionContract,
    ReportDataContract,
    ReportDataProvider,
    report_data_providers,
)
from app.modules.safety.models import SafetyRecord, SafetyRecordStatus
from app.modules.workforce.attendance_models import (
    AttendanceEntry,
    AttendanceMarkStatus,
    AttendanceRegister,
    AttendanceRegisterStatus,
)
from app.modules.workforce.models import Crew, Worker

DPR_REPORT_TYPE_KEY = "field.dpr"


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    if isinstance(value, list | tuple | set):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def _typed_custom_field_value(row: CustomFieldValue) -> object:
    if row.text_value is not None:
        return row.text_value
    if row.numeric_value is not None:
        if row.currency_code:
            return {"amount": format(row.numeric_value, "f"), "currency": row.currency_code}
        if row.unit_code:
            return {"value": format(row.numeric_value, "f"), "unit": row.unit_code}
        return format(row.numeric_value, "f")
    if row.boolean_value is not None:
        return row.boolean_value
    if row.date_value is not None:
        return row.date_value.isoformat()
    if row.datetime_value is not None:
        return row.datetime_value.isoformat()
    if row.uuid_value is not None:
        return str(row.uuid_value)
    return row.json_value


async def _timezone_name(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project: Project,
) -> str:
    if project.timezone:
        return project.timezone
    settings = await db.get(OrganizationSettings, organization_id)
    return settings.timezone if settings else "Asia/Kolkata"


def _local_day_bounds(report_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(report_date, time.min, tzinfo=zone)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


async def _client(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> tuple[Party | None, dict[str, object] | None]:
    assignment = await db.scalar(
        select(ProjectPartyAssignment)
        .where(
            ProjectPartyAssignment.organization_id == organization_id,
            ProjectPartyAssignment.project_id == project_id,
            ProjectPartyAssignment.role == ProjectPartyRole.CLIENT,
            ProjectPartyAssignment.active.is_(True),
        )
        .order_by(ProjectPartyAssignment.created_at, ProjectPartyAssignment.id)
        .limit(1)
    )
    if assignment is None:
        return None, None
    party = await db.scalar(
        select(Party).where(
            Party.organization_id == organization_id,
            Party.id == assignment.party_id,
        )
    )
    if party is None:
        return None, None
    logo_link = await db.scalar(
        select(FileLink)
        .where(
            FileLink.organization_id == organization_id,
            FileLink.entity_type == "commercial_party",
            FileLink.entity_id == party.id,
            FileLink.relation_type == "logo",
        )
        .order_by(FileLink.created_at.desc())
        .limit(1)
    )
    logo = None
    if logo_link:
        logo = {
            "asset_id": str(logo_link.asset_id),
            "version": logo_link.pinned_version,
        }
    return party, logo


async def _user_names(db: AsyncSession, user_ids: set[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    rows = await db.scalars(select(User).where(User.id.in_(user_ids)))
    return {row.id: row.display_name for row in rows.all()}


async def _approval_names(
    db: AsyncSession,
    *,
    report: DailyReport,
) -> dict[str, object]:
    prepared_user_id = await db.scalar(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == report.organization_id,
            OrganizationMembership.id == report.prepared_by_membership_id,
        )
    )
    history = list(
        (
            await db.scalars(
                select(DailyReportHistoryEvent)
                .where(
                    DailyReportHistoryEvent.organization_id == report.organization_id,
                    DailyReportHistoryEvent.daily_report_id == report.id,
                )
                .order_by(DailyReportHistoryEvent.created_at, DailyReportHistoryEvent.id)
            )
        ).all()
    )
    submitted_actor = next(
        (row.actor_user_id for row in reversed(history) if row.event_type == DailyReportHistoryType.SUBMITTED),
        None,
    )
    review_event = next(
        (
            row
            for row in reversed(history)
            if row.event_type in {DailyReportHistoryType.APPROVED, DailyReportHistoryType.REJECTED}
        ),
        None,
    )
    ids = {item for item in (prepared_user_id, submitted_actor, review_event.actor_user_id if review_event else None) if item}
    names = await _user_names(db, ids)
    approved_user_id = (
        review_event.actor_user_id
        if review_event and review_event.event_type == DailyReportHistoryType.APPROVED
        else None
    )
    return {
        "prepared_by": names.get(prepared_user_id) if prepared_user_id else None,
        "submitted_by": names.get(submitted_actor) if submitted_actor else None,
        "reviewed_by": names.get(review_event.actor_user_id) if review_event and review_event.actor_user_id else None,
        "approved_by": names.get(approved_user_id) if approved_user_id else None,
        "submitted_at": _json_value(report.submitted_at),
        "approved_at": _json_value(report.approved_at),
    }


async def _custom_fields_for_entity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> dict[str, object]:
    rows = await db.execute(
        select(CustomFieldDefinition, CustomFieldValue)
        .join(
            CustomFieldValue,
            and_(
                CustomFieldValue.definition_id == CustomFieldDefinition.id,
                CustomFieldValue.organization_id == CustomFieldDefinition.organization_id,
                CustomFieldValue.entity_id == entity_id,
            ),
            isouter=True,
        )
        .where(
            CustomFieldDefinition.organization_id == organization_id,
            CustomFieldDefinition.entity_type == entity_type,
            CustomFieldDefinition.active.is_(True),
            CustomFieldDefinition.reportable.is_(True),
        )
        .order_by(CustomFieldDefinition.display_order, CustomFieldDefinition.key)
    )
    result: dict[str, object] = {}
    for definition, value in rows.all():
        result[definition.key] = _typed_custom_field_value(value) if value is not None else None
    return result


async def _workforce(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> tuple[list[dict[str, object]], dict[str, object]]:
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
        return [], {
            "total_workers": 0,
            "total_present": 0,
            "total_absent": 0,
            "total_regular_hours": "0",
            "total_overtime_hours": "0",
            "total_labour_hours": "0",
        }
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
    worker_ids = {row.worker_id for row in entries}
    crew_ids = {row.crew_id for row in entries if row.crew_id}
    employer_ids = {row.employer_party_id for row in entries if row.employer_party_id}
    wbs_ids = {row.wbs_code_id for row in entries if row.wbs_code_id}
    workers = await db.scalars(
        select(Worker).where(Worker.organization_id == organization_id, Worker.id.in_(worker_ids))
    ) if worker_ids else None
    crews = await db.scalars(
        select(Crew).where(Crew.organization_id == organization_id, Crew.id.in_(crew_ids))
    ) if crew_ids else None
    parties = await db.scalars(
        select(Party).where(Party.organization_id == organization_id, Party.id.in_(employer_ids))
    ) if employer_ids else None
    wbs_rows = await db.scalars(
        select(WBSCode).where(WBSCode.organization_id == organization_id, WBSCode.id.in_(wbs_ids))
    ) if wbs_ids else None
    worker_map = {row.id: row for row in workers.all()} if workers else {}
    crew_map = {row.id: row.name for row in crews.all()} if crews else {}
    party_map = {row.id: row.name for row in parties.all()} if parties else {}
    wbs_map = {row.id: row for row in wbs_rows.all()} if wbs_rows else {}

    grouped: dict[tuple[str, str, str, str], dict[str, object]] = defaultdict(
        lambda: {
            "worker_count": 0,
            "present_count": 0,
            "absent_count": 0,
            "regular_hours": Decimal(0),
            "overtime_hours": Decimal(0),
        }
    )
    working = {AttendanceMarkStatus.PRESENT, AttendanceMarkStatus.HALF_DAY}
    total_present = 0
    total_absent = 0
    total_regular = Decimal(0)
    total_overtime = Decimal(0)
    for entry in entries:
        worker = worker_map.get(entry.worker_id)
        trade = entry.trade or (worker.trade if worker else None) or "Unspecified"
        employer = party_map.get(entry.employer_party_id, "Direct") if entry.employer_party_id else "Direct"
        crew = crew_map.get(entry.crew_id, "Unassigned") if entry.crew_id else "Unassigned"
        wbs = wbs_map.get(entry.wbs_code_id) if entry.wbs_code_id else None
        wbs_code = wbs.code if wbs else ""
        key = (employer, trade, crew, wbs_code)
        group = grouped[key]
        group["worker_count"] = int(group["worker_count"]) + 1
        if entry.mark_status in working:
            group["present_count"] = int(group["present_count"]) + 1
            total_present += 1
        if entry.mark_status == AttendanceMarkStatus.ABSENT:
            group["absent_count"] = int(group["absent_count"]) + 1
            total_absent += 1
        group["regular_hours"] = Decimal(group["regular_hours"]) + entry.regular_hours
        group["overtime_hours"] = Decimal(group["overtime_hours"]) + entry.overtime_hours
        total_regular += entry.regular_hours
        total_overtime += entry.overtime_hours

    rows: list[dict[str, object]] = []
    for (employer, trade, crew, wbs_code), group in sorted(grouped.items()):
        regular = Decimal(group["regular_hours"])
        overtime = Decimal(group["overtime_hours"])
        rows.append(
            {
                "employer": employer,
                "trade": trade,
                "crew": crew,
                "wbs_code": wbs_code,
                "worker_count": int(group["worker_count"]),
                "present_count": int(group["present_count"]),
                "absent_count": int(group["absent_count"]),
                "regular_hours": format(regular, "f"),
                "overtime_hours": format(overtime, "f"),
                "total_hours": format(regular + overtime, "f"),
            }
        )
    return rows, {
        "total_workers": len(entries),
        "total_present": total_present,
        "total_absent": total_absent,
        "total_regular_hours": format(total_regular, "f"),
        "total_overtime_hours": format(total_overtime, "f"),
        "total_labour_hours": format(total_regular + total_overtime, "f"),
    }


async def _work_progress(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> list[dict[str, object]]:
    rows = list(
        (
            await db.scalars(
                select(DPRWorkProgressEntry)
                .where(
                    DPRWorkProgressEntry.organization_id == organization_id,
                    DPRWorkProgressEntry.project_id == report.project_id,
                    DPRWorkProgressEntry.daily_report_id == report.id,
                )
                .order_by(DPRWorkProgressEntry.created_at, DPRWorkProgressEntry.id)
            )
        ).all()
    )
    wbs_ids = {row.wbs_code_id for row in rows if row.wbs_code_id}
    boq_ids = {row.boq_item_id for row in rows if row.boq_item_id}
    wbs_rows = await db.scalars(
        select(WBSCode).where(WBSCode.organization_id == organization_id, WBSCode.id.in_(wbs_ids))
    ) if wbs_ids else None
    boq_rows = await db.scalars(
        select(BOQItem).where(BOQItem.organization_id == organization_id, BOQItem.id.in_(boq_ids))
    ) if boq_ids else None
    wbs_map = {row.id: row for row in wbs_rows.all()} if wbs_rows else {}
    boq_map = {row.id: row for row in boq_rows.all()} if boq_rows else {}
    result = [
        {
            "description": row.description,
            "wbs_code": wbs_map[row.wbs_code_id].code if row.wbs_code_id in wbs_map else None,
            "wbs_name": wbs_map[row.wbs_code_id].name if row.wbs_code_id in wbs_map else None,
            "boq_item_code": boq_map[row.boq_item_id].item_code if row.boq_item_id in boq_map else None,
            "boq_description": boq_map[row.boq_item_id].description if row.boq_item_id in boq_map else None,
            "location": row.location,
            "quantity": _json_value(row.quantity),
            "unit_code": row.unit_code,
            "remarks": row.remarks,
        }
        for row in rows
    ]
    if result:
        return result
    legacy = await db.scalars(
        select(DailyReportWorkEntry)
        .where(
            DailyReportWorkEntry.organization_id == organization_id,
            DailyReportWorkEntry.daily_report_id == report.id,
        )
        .order_by(DailyReportWorkEntry.created_at, DailyReportWorkEntry.id)
    )
    return [
        {
            "description": row.description,
            "wbs_code": row.cost_code,
            "wbs_name": None,
            "boq_item_code": None,
            "boq_description": None,
            "location": row.location,
            "quantity": _json_value(row.quantity),
            "unit_code": row.unit_code,
            "remarks": row.notes,
        }
        for row in legacy.all()
    ]


async def _materials_received(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project: Project,
    report_date: date,
) -> list[dict[str, object]]:
    start_utc, end_utc = _local_day_bounds(
        report_date,
        await _timezone_name(db, organization_id=organization_id, project=project),
    )
    rows = await db.execute(
        select(GoodsReceipt, GoodsReceiptLine, PurchaseOrderLine, PurchaseOrder, Material, Party, WBSCode)
        .join(GoodsReceiptLine, GoodsReceiptLine.goods_receipt_id == GoodsReceipt.id)
        .join(PurchaseOrderLine, PurchaseOrderLine.id == GoodsReceiptLine.purchase_order_line_id)
        .join(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
        .join(Party, Party.id == PurchaseOrder.supplier_party_id)
        .join(Material, Material.id == PurchaseOrderLine.material_id, isouter=True)
        .join(WBSCode, WBSCode.id == PurchaseOrderLine.wbs_code_id, isouter=True)
        .where(
            GoodsReceipt.organization_id == organization_id,
            GoodsReceipt.project_id == project.id,
            GoodsReceipt.status == GoodsReceiptStatus.RECEIVED,
            GoodsReceipt.received_at >= start_utc,
            GoodsReceipt.received_at < end_utc,
        )
        .order_by(GoodsReceipt.received_at, GoodsReceipt.number, GoodsReceiptLine.id)
    )
    result: list[dict[str, object]] = []
    for grn, line, po_line, po, material, supplier, wbs in rows.all():
        result.append(
            {
                "grn_number": grn.number,
                "po_number": po.number,
                "supplier": supplier.name,
                "material": material.name if material else po_line.description,
                "received_quantity": format(line.received_quantity, "f"),
                "accepted_quantity": format(line.accepted_quantity, "f"),
                "rejected_quantity": format(line.rejected_quantity, "f"),
                "unit_code": line.unit_code,
                "wbs_code": wbs.code if wbs else None,
                "challan_number": grn.challan_number,
                "received_at": grn.received_at.isoformat(),
                "remarks": line.remarks,
            }
        )
    return result


async def _materials_consumed(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> list[dict[str, object]]:
    rows = await db.execute(
        select(MaterialConsumption, Material, WBSCode, BOQItem)
        .join(Material, Material.id == MaterialConsumption.material_id)
        .join(WBSCode, WBSCode.id == MaterialConsumption.wbs_code_id, isouter=True)
        .join(BOQItem, BOQItem.id == MaterialConsumption.boq_item_id, isouter=True)
        .where(
            MaterialConsumption.organization_id == organization_id,
            MaterialConsumption.project_id == report.project_id,
            MaterialConsumption.consumption_date == report.report_date,
            MaterialConsumption.status == MaterialConsumptionStatus.POSTED,
        )
        .order_by(Material.name, MaterialConsumption.created_at)
    )
    return [
        {
            "material": material.name,
            "quantity": format(source.quantity, "f"),
            "unit_code": source.unit_code,
            "wbs_code": wbs.code if wbs else None,
            "boq_item_code": boq.item_code if boq else None,
            "location": source.location,
            "remarks": source.notes,
        }
        for source, material, wbs, boq in rows.all()
    ]


async def _equipment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
) -> list[dict[str, object]]:
    rows = await db.execute(
        select(EquipmentUsage, ProjectEquipmentAssignment, EquipmentAsset, WBSCode, BOQItem)
        .join(ProjectEquipmentAssignment, ProjectEquipmentAssignment.id == EquipmentUsage.equipment_assignment_id)
        .join(EquipmentAsset, EquipmentAsset.id == ProjectEquipmentAssignment.equipment_asset_id)
        .join(WBSCode, WBSCode.id == EquipmentUsage.wbs_code_id, isouter=True)
        .join(BOQItem, BOQItem.id == EquipmentUsage.boq_item_id, isouter=True)
        .where(
            EquipmentUsage.organization_id == organization_id,
            EquipmentUsage.project_id == report.project_id,
            EquipmentUsage.usage_date == report.report_date,
            EquipmentUsage.shift_code == report.shift_code,
            EquipmentUsage.status == EquipmentUsageStatus.POSTED,
        )
        .order_by(EquipmentAsset.asset_number, EquipmentUsage.created_at)
    )
    return [
        {
            "asset_number": asset.asset_number,
            "equipment": asset.name,
            "category": asset.category,
            "operating_hours": _json_value(source.operating_hours),
            "meter_start": _json_value(source.meter_start),
            "meter_end": _json_value(source.meter_end),
            "wbs_code": wbs.code if wbs else None,
            "boq_item_code": boq.item_code if boq else None,
            "location": source.location,
            "remarks": source.notes,
        }
        for source, assignment, asset, wbs, boq in rows.all()
    ]


async def _delays(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report_id: UUID,
) -> list[dict[str, object]]:
    rows = await db.scalars(
        select(DailyReportDelayEntry)
        .where(
            DailyReportDelayEntry.organization_id == organization_id,
            DailyReportDelayEntry.daily_report_id == report_id,
        )
        .order_by(DailyReportDelayEntry.created_at, DailyReportDelayEntry.id)
    )
    return [
        {
            "category": row.category,
            "description": row.description,
            "started_at": _json_value(row.started_at),
            "ended_at": _json_value(row.ended_at),
            "lost_hours": _json_value(row.lost_hours),
            "responsible_party": row.responsible_party,
            "schedule_impact": row.schedule_impact,
            "remarks": row.notes,
        }
        for row in rows.all()
    ]


async def _safety(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project: Project,
    report: DailyReport,
) -> list[dict[str, object]]:
    start_utc, end_utc = _local_day_bounds(
        report.report_date,
        await _timezone_name(db, organization_id=organization_id, project=project),
    )
    records = list(
        (
            await db.scalars(
                select(SafetyRecord)
                .where(
                    SafetyRecord.organization_id == organization_id,
                    SafetyRecord.project_id == report.project_id,
                    SafetyRecord.status != SafetyRecordStatus.VOID,
                    SafetyRecord.occurred_at.is_not(None),
                    SafetyRecord.occurred_at >= start_utc,
                    SafetyRecord.occurred_at < end_utc,
                )
                .order_by(SafetyRecord.occurred_at, SafetyRecord.number)
            )
        ).all()
    )
    result = [
        {
            "number": str(row.number),
            "type": row.record_type.value,
            "title": row.title,
            "severity": row.severity.value,
            "status": row.status.value,
            "location": row.location,
            "occurred_at": _json_value(row.occurred_at),
            "description": row.description,
        }
        for row in records
    ]
    authoritative_ids = {row.id for row in records}
    manual = await db.scalars(
        select(DailyReportSafetyEntry)
        .where(
            DailyReportSafetyEntry.organization_id == organization_id,
            DailyReportSafetyEntry.daily_report_id == report.id,
            or_(
                DailyReportSafetyEntry.safety_record_id.is_(None),
                DailyReportSafetyEntry.safety_record_id.not_in(authoritative_ids) if authoritative_ids else True,
            ),
        )
        .order_by(DailyReportSafetyEntry.created_at, DailyReportSafetyEntry.id)
    )
    result.extend(
        {
            "number": None,
            "type": row.entry_type,
            "title": row.summary,
            "severity": row.severity,
            "status": "dpr_observation",
            "location": None,
            "occurred_at": None,
            "description": row.notes,
        }
        for row in manual.all()
    )
    return result


async def _photos(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report_id: UUID,
) -> list[dict[str, object]]:
    rows = await db.scalars(
        select(FileLink)
        .where(
            FileLink.organization_id == organization_id,
            FileLink.entity_type == "daily_report",
            FileLink.entity_id == report_id,
            FileLink.relation_type.in_(("photo", "attachment")),
        )
        .order_by(FileLink.created_at, FileLink.id)
    )
    return [
        {
            "asset_id": str(row.asset_id),
            "version": row.pinned_version,
            "relation_type": row.relation_type,
        }
        for row in rows.all()
    ]


async def build_dpr_payload(
    db: AsyncSession,
    organization_id: UUID,
    project_id: UUID | None,
    source_entity_id: UUID,
) -> dict[str, object]:
    if project_id is None:
        raise ValueError("DPR payload requires a project")
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == source_entity_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        raise ValueError("Daily Progress Report was not found")
    organization = await db.get(Organization, organization_id)
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if organization is None or project is None:
        raise ValueError("DPR company or project was not found")
    client, client_logo = await _client(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    branding = await db.scalar(
        select(ReportBrandingProfile).where(ReportBrandingProfile.organization_id == organization_id)
    )
    company_logo = None
    if branding and branding.company_logo_asset_id:
        company_logo = {
            "asset_id": str(branding.company_logo_asset_id),
            "version": branding.company_logo_version,
        }
    workforce, workforce_summary = await _workforce(
        db,
        organization_id=organization_id,
        report=report,
    )
    work_progress = await _work_progress(db, organization_id=organization_id, report=report)
    materials_received = await _materials_received(
        db,
        organization_id=organization_id,
        project=project,
        report_date=report.report_date,
    )
    materials_consumed = await _materials_consumed(
        db,
        organization_id=organization_id,
        report=report,
    )
    equipment = await _equipment(db, organization_id=organization_id, report=report)
    delays = await _delays(db, organization_id=organization_id, report_id=report.id)
    safety = await _safety(
        db,
        organization_id=organization_id,
        project=project,
        report=report,
    )
    photos = await _photos(db, organization_id=organization_id, report_id=report.id)
    approvals = await _approval_names(db, report=report)
    custom_fields = {
        "report": await _custom_fields_for_entity(
            db,
            organization_id=organization_id,
            entity_type="daily_report",
            entity_id=report.id,
        ),
        "project": await _custom_fields_for_entity(
            db,
            organization_id=organization_id,
            entity_type="project",
            entity_id=project.id,
        ),
        "company": await _custom_fields_for_entity(
            db,
            organization_id=organization_id,
            entity_type="organization",
            entity_id=organization.id,
        ),
    }
    project_address = ", ".join(
        part
        for part in (
            project.address_line_1,
            project.address_line_2,
            project.locality,
            project.region,
            project.postal_code,
            project.country_code,
        )
        if part
    )
    summary = {
        **workforce_summary,
        "work_progress_count": len(work_progress),
        "materials_received_count": len(materials_received),
        "materials_consumed_count": len(materials_consumed),
        "equipment_count": len(equipment),
        "delay_count": len(delays),
        "safety_count": len(safety),
        "photo_count": len(photos),
    }
    display_company_name = branding.company_display_name if branding and branding.company_display_name else organization.name
    return {
        "schema_version": 1,
        "company": {
            "id": str(organization.id),
            "name": display_company_name,
            "legal_name": organization.legal_name,
            "logo": company_logo,
        },
        "project": {
            "id": str(project.id),
            "number": project.number,
            "name": project.name,
            "address": project_address,
            "client_name": client.name if client else None,
            "client_legal_name": client.legal_name if client else None,
            "client_logo": client_logo,
        },
        "report": {
            "id": str(report.id),
            "number": f"{project.number}-DPR-{report.report_date.strftime('%Y%m%d')}-{report.shift_code.upper()}",
            "date": report.report_date.isoformat(),
            "shift": report.shift_code,
            "status": report.status.value,
            "revision": report.revision,
            "weather_condition": report.weather_condition,
            "temperature_low": _json_value(report.temperature_low),
            "temperature_high": _json_value(report.temperature_high),
            "temperature_unit": report.temperature_unit,
            "notes": report.notes,
        },
        "approvals": approvals,
        "workforce": workforce,
        "work_progress": work_progress,
        "materials_received": materials_received,
        "materials_consumed": materials_consumed,
        "equipment": equipment,
        "delays": delays,
        "safety": safety,
        "quality": [],
        "photos": photos,
        "summary": summary,
        "custom_fields": custom_fields,
    }


DPR_CONTRACT = ReportDataContract(
    key=DPR_REPORT_TYPE_KEY,
    version=1,
    scalar_paths=(
        "company.id",
        "company.name",
        "company.legal_name",
        "company.logo",
        "project.id",
        "project.number",
        "project.name",
        "project.address",
        "project.client_name",
        "project.client_legal_name",
        "project.client_logo",
        "report.id",
        "report.number",
        "report.date",
        "report.shift",
        "report.status",
        "report.revision",
        "report.weather_condition",
        "report.temperature_low",
        "report.temperature_high",
        "report.temperature_unit",
        "report.notes",
        "approvals.prepared_by",
        "approvals.submitted_by",
        "approvals.reviewed_by",
        "approvals.approved_by",
        "approvals.submitted_at",
        "approvals.approved_at",
        "summary.total_workers",
        "summary.total_present",
        "summary.total_absent",
        "summary.total_regular_hours",
        "summary.total_overtime_hours",
        "summary.total_labour_hours",
        "summary.work_progress_count",
        "summary.materials_received_count",
        "summary.materials_consumed_count",
        "summary.equipment_count",
        "summary.delay_count",
        "summary.safety_count",
        "summary.photo_count",
    ),
    collections=(
        CollectionContract(
            key="workforce",
            fields=(
                "employer",
                "trade",
                "crew",
                "wbs_code",
                "worker_count",
                "present_count",
                "absent_count",
                "regular_hours",
                "overtime_hours",
                "total_hours",
            ),
        ),
        CollectionContract(
            key="work_progress",
            fields=(
                "description",
                "wbs_code",
                "wbs_name",
                "boq_item_code",
                "boq_description",
                "location",
                "quantity",
                "unit_code",
                "remarks",
            ),
        ),
        CollectionContract(
            key="materials_received",
            fields=(
                "grn_number",
                "po_number",
                "supplier",
                "material",
                "received_quantity",
                "accepted_quantity",
                "rejected_quantity",
                "unit_code",
                "wbs_code",
                "challan_number",
                "received_at",
                "remarks",
            ),
        ),
        CollectionContract(
            key="materials_consumed",
            fields=(
                "material",
                "quantity",
                "unit_code",
                "wbs_code",
                "boq_item_code",
                "location",
                "remarks",
            ),
        ),
        CollectionContract(
            key="equipment",
            fields=(
                "asset_number",
                "equipment",
                "category",
                "operating_hours",
                "meter_start",
                "meter_end",
                "wbs_code",
                "boq_item_code",
                "location",
                "remarks",
            ),
        ),
        CollectionContract(
            key="delays",
            fields=(
                "category",
                "description",
                "started_at",
                "ended_at",
                "lost_hours",
                "responsible_party",
                "schedule_impact",
                "remarks",
            ),
        ),
        CollectionContract(
            key="safety",
            fields=(
                "number",
                "type",
                "title",
                "severity",
                "status",
                "location",
                "occurred_at",
                "description",
            ),
        ),
        CollectionContract(key="quality", fields=("number", "type", "title", "status", "description")),
        CollectionContract(key="photos", fields=("asset_id", "version", "relation_type")),
    ),
    dynamic_prefixes=("custom_fields.",),
    required_permission_key="field.daily_report.view",
)


if not report_data_providers.contains(DPR_REPORT_TYPE_KEY):
    report_data_providers.register(
        ReportDataProvider(
            contract=DPR_CONTRACT,
            source_entity_type="daily_report",
            build_payload=build_dpr_payload,
        )
    )
