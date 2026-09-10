from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQItem, WBSCode
from app.modules.equipment.models import ProjectEquipmentAssignment
from app.modules.equipment.usage_models import (
    EquipmentUsage,
    EquipmentUsageStatus,
    ProjectEquipmentRate,
)
from app.modules.events.service import enqueue_event
from app.modules.projects.models import (
    Project,
    ProjectMembership,
    ProjectMembershipStatus,
)


class EquipmentUsageValidationError(ValueError):
    pass


class EquipmentUsageConflictError(EquipmentUsageValidationError):
    pass


async def _project(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> Project:
    row = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if row is None:
        raise EquipmentUsageValidationError("Project was not found")
    return row


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    member = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if member is None:
        raise EquipmentUsageValidationError(
            "Active project membership is required for equipment usage"
        )


async def _assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
) -> ProjectEquipmentAssignment:
    row = await db.scalar(
        select(ProjectEquipmentAssignment).where(
            ProjectEquipmentAssignment.id == assignment_id,
            ProjectEquipmentAssignment.organization_id == organization_id,
            ProjectEquipmentAssignment.project_id == project_id,
        )
    )
    if row is None:
        raise EquipmentUsageValidationError(
            "Equipment assignment was not found in this project"
        )
    return row


def _date_within_assignment(
    assignment: ProjectEquipmentAssignment,
    value: date,
    *,
    field_name: str,
) -> None:
    if assignment.start_date is not None and value < assignment.start_date:
        raise EquipmentUsageValidationError(
            f"{field_name} cannot be before the equipment assignment start date"
        )
    if assignment.end_date is not None and value > assignment.end_date:
        raise EquipmentUsageValidationError(
            f"{field_name} cannot be after the equipment assignment end date"
        )


async def _validate_work_refs(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    wbs_code_id: UUID | None,
    boq_item_id: UUID | None,
) -> None:
    if wbs_code_id is not None:
        exists = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_code_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if exists is None:
            raise EquipmentUsageValidationError(
                "WBS/Cost Code was not found in this project"
            )
    if boq_item_id is not None:
        exists = await db.scalar(
            select(BOQItem.id).where(
                BOQItem.id == boq_item_id,
                BOQItem.organization_id == organization_id,
                BOQItem.project_id == project_id,
            )
        )
        if exists is None:
            raise EquipmentUsageValidationError("BOQ item was not found in this project")


async def create_equipment_rate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> ProjectEquipmentRate:
    project = await _project(db, organization_id=organization_id, project_id=project_id)
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    assignment = await _assignment(
        db,
        organization_id=organization_id,
        project_id=project_id,
        assignment_id=assignment_id,
    )

    effective_from = values.get("effective_from")
    effective_to = values.get("effective_to")
    if not isinstance(effective_from, date):
        raise EquipmentUsageValidationError("effective_from is required")
    if effective_to is not None and not isinstance(effective_to, date):
        raise EquipmentUsageValidationError("effective_to must be a date")
    _date_within_assignment(assignment, effective_from, field_name="effective_from")
    if isinstance(effective_to, date):
        _date_within_assignment(assignment, effective_to, field_name="effective_to")
        if effective_to < effective_from:
            raise EquipmentUsageValidationError(
                "effective_to must be on or after effective_from"
            )

    overlap_conditions = [
        ProjectEquipmentRate.organization_id == organization_id,
        ProjectEquipmentRate.project_id == project_id,
        ProjectEquipmentRate.equipment_assignment_id == assignment_id,
        or_(
            ProjectEquipmentRate.effective_to.is_(None),
            ProjectEquipmentRate.effective_to >= effective_from,
        ),
    ]
    if isinstance(effective_to, date):
        overlap_conditions.append(ProjectEquipmentRate.effective_from <= effective_to)
    overlap = await db.scalar(select(ProjectEquipmentRate.id).where(*overlap_conditions))
    if overlap is not None:
        raise EquipmentUsageConflictError(
            "Equipment rate period overlaps an existing rate for this assignment"
        )

    payload = dict(values)
    payload.pop("organization_id", None)
    payload.pop("project_id", None)
    payload.pop("equipment_assignment_id", None)
    payload.pop("currency_code", None)
    payload.pop("revision", None)
    row = ProjectEquipmentRate(
        organization_id=organization_id,
        project_id=project_id,
        equipment_assignment_id=assignment_id,
        currency_code=(project.currency_code or "INR").upper(),
        **payload,
    )
    db.add(row)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.rate.created",
        target_type="project_equipment_rate",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "equipment_assignment_id": str(assignment_id),
            "rate_basis": row.rate_basis.value,
            "rate": row.rate,
            "currency_code": row.currency_code,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        },
    )
    return row


async def end_equipment_rate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    rate_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    effective_to: date,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectEquipmentRate:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    assignment = await _assignment(
        db,
        organization_id=organization_id,
        project_id=project_id,
        assignment_id=assignment_id,
    )
    row = await db.scalar(
        select(ProjectEquipmentRate)
        .where(
            ProjectEquipmentRate.id == rate_id,
            ProjectEquipmentRate.organization_id == organization_id,
            ProjectEquipmentRate.project_id == project_id,
            ProjectEquipmentRate.equipment_assignment_id == assignment_id,
        )
        .with_for_update()
    )
    if row is None:
        raise EquipmentUsageValidationError("Equipment rate was not found")
    if row.revision != expected_revision:
        raise EquipmentUsageConflictError("Equipment rate was changed by another user")
    if effective_to < row.effective_from:
        raise EquipmentUsageValidationError(
            "effective_to cannot be before the equipment rate start date"
        )
    _date_within_assignment(assignment, effective_to, field_name="effective_to")

    next_rate = await db.scalar(
        select(ProjectEquipmentRate.id).where(
            ProjectEquipmentRate.organization_id == organization_id,
            ProjectEquipmentRate.project_id == project_id,
            ProjectEquipmentRate.equipment_assignment_id == assignment_id,
            ProjectEquipmentRate.id != rate_id,
            ProjectEquipmentRate.effective_from <= effective_to,
            or_(
                ProjectEquipmentRate.effective_to.is_(None),
                ProjectEquipmentRate.effective_to >= row.effective_from,
            ),
        )
    )
    if next_rate is not None:
        raise EquipmentUsageConflictError(
            "Ending this rate on that date would overlap another equipment rate"
        )

    row.effective_to = effective_to
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.rate.ended",
        target_type="project_equipment_rate",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"effective_to": effective_to.isoformat(), "revision": row.revision},
    )
    return row


async def create_equipment_usage(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> EquipmentUsage:
    await _project(db, organization_id=organization_id, project_id=project_id)
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    assignment_id = values.get("equipment_assignment_id")
    usage_date = values.get("usage_date")
    if not isinstance(assignment_id, UUID):
        raise EquipmentUsageValidationError("equipment_assignment_id is required")
    if not isinstance(usage_date, date):
        raise EquipmentUsageValidationError("usage_date is required")
    assignment = await _assignment(
        db,
        organization_id=organization_id,
        project_id=project_id,
        assignment_id=assignment_id,
    )
    _date_within_assignment(assignment, usage_date, field_name="usage_date")
    wbs_code_id = values.get("wbs_code_id")
    boq_item_id = values.get("boq_item_id")
    await _validate_work_refs(
        db,
        organization_id=organization_id,
        project_id=project_id,
        wbs_code_id=wbs_code_id if isinstance(wbs_code_id, UUID) else None,
        boq_item_id=boq_item_id if isinstance(boq_item_id, UUID) else None,
    )

    shift_code = str(values.get("shift_code") or "day").strip()
    duplicate = await db.scalar(
        select(EquipmentUsage.id).where(
            EquipmentUsage.organization_id == organization_id,
            EquipmentUsage.project_id == project_id,
            EquipmentUsage.equipment_assignment_id == assignment_id,
            EquipmentUsage.usage_date == usage_date,
            EquipmentUsage.shift_code == shift_code,
        )
    )
    if duplicate is not None:
        raise EquipmentUsageConflictError(
            "Equipment usage already exists for this assignment, date and shift"
        )

    payload = dict(values)
    for key in (
        "organization_id",
        "project_id",
        "status",
        "revision",
        "created_by_membership_id",
        "posted_by_membership_id",
        "posted_at",
    ):
        payload.pop(key, None)
    payload["shift_code"] = shift_code
    row = EquipmentUsage(
        organization_id=organization_id,
        project_id=project_id,
        status=EquipmentUsageStatus.DRAFT,
        created_by_membership_id=membership_id,
        **payload,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.usage.created",
        target_type="equipment_usage",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "project_id": str(project_id),
            "equipment_assignment_id": str(assignment_id),
            "usage_date": usage_date.isoformat(),
            "operating_hours": row.operating_hours,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="equipment.usage.changed",
        entity_type="equipment_usage",
        entity_id=row.id,
        entity_version=row.revision,
        required_permission_key="equipment.usage.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"status": row.status.value},
    )
    return row


async def post_equipment_usage(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    usage_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> EquipmentUsage:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    row = await db.scalar(
        select(EquipmentUsage)
        .where(
            EquipmentUsage.id == usage_id,
            EquipmentUsage.organization_id == organization_id,
            EquipmentUsage.project_id == project_id,
        )
        .with_for_update()
    )
    if row is None:
        raise EquipmentUsageValidationError("Equipment usage was not found")
    if row.revision != expected_revision:
        raise EquipmentUsageConflictError("Equipment usage was changed by another user")
    if row.status != EquipmentUsageStatus.DRAFT:
        raise EquipmentUsageValidationError("Only draft equipment usage can be posted")

    assignment = await _assignment(
        db,
        organization_id=organization_id,
        project_id=project_id,
        assignment_id=row.equipment_assignment_id,
    )
    _date_within_assignment(assignment, row.usage_date, field_name="usage_date")
    await _validate_work_refs(
        db,
        organization_id=organization_id,
        project_id=project_id,
        wbs_code_id=row.wbs_code_id,
        boq_item_id=row.boq_item_id,
    )

    row.status = EquipmentUsageStatus.POSTED
    row.posted_by_membership_id = membership_id
    row.posted_at = datetime.now(UTC)
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.usage.posted",
        target_type="equipment_usage",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "project_id": str(project_id),
            "equipment_assignment_id": str(row.equipment_assignment_id),
            "usage_date": row.usage_date.isoformat(),
            "operating_hours": row.operating_hours,
            "revision": row.revision,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="equipment.usage.posted",
        entity_type="equipment_usage",
        entity_id=row.id,
        entity_version=row.revision,
        required_permission_key="equipment.usage.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"status": row.status.value},
    )
    return row
