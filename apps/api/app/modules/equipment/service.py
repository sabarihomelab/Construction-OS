from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.equipment.models import (
    EquipmentAsset,
    EquipmentAssignmentStatus,
    EquipmentMaintenance,
    EquipmentStatus,
    MaintenanceStatus,
    Material,
    MaterialDelivery,
    MaterialDeliveryStatus,
    ProjectEquipmentAssignment,
    ProjectMaterialPlan,
)
from app.modules.events.service import enqueue_event
from app.modules.identity.models import OrganizationMembership
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index
from app.modules.workforce.models import Worker


class EquipmentValidationError(ValueError):
    pass


class EquipmentConflictError(EquipmentValidationError):
    pass


def _clean(value: object, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise EquipmentValidationError("Required text value is missing")
        return None
    result = str(value).strip()
    if required and not result:
        raise EquipmentValidationError("Required text value is blank")
    return result or None


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    found = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if found is None:
        raise EquipmentValidationError("Project was not found")


async def _require_asset(
    db: AsyncSession,
    organization_id: UUID,
    asset_id: UUID,
    *,
    lock: bool = False,
) -> EquipmentAsset:
    statement = select(EquipmentAsset).where(
        EquipmentAsset.id == asset_id,
        EquipmentAsset.organization_id == organization_id,
    )
    if lock:
        statement = statement.with_for_update()
    asset = await db.scalar(statement)
    if asset is None:
        raise EquipmentValidationError("Equipment asset was not found")
    return asset


async def _require_material(
    db: AsyncSession,
    organization_id: UUID,
    material_id: UUID,
    *,
    lock: bool = False,
) -> Material:
    statement = select(Material).where(
        Material.id == material_id,
        Material.organization_id == organization_id,
    )
    if lock:
        statement = statement.with_for_update()
    material = await db.scalar(statement)
    if material is None:
        raise EquipmentValidationError("Material was not found")
    return material


async def _require_project_membership(
    db: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    found = await db.scalar(
        select(OrganizationMembership.id)
        .join(
            Project,
            Project.organization_id == OrganizationMembership.organization_id,
        )
        .where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
            Project.id == project_id,
        )
    )
    if found is None:
        raise EquipmentValidationError("Membership was not found in this company/project context")


async def _publish(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID | None,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    revision: int,
    permission: str,
    actor_user_id: UUID | None,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=revision,
        required_permission_key=permission,
        scope_type="project" if project_id is not None else None,
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"id": str(entity_id), "revision": revision},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=revision,
    )


async def create_equipment_asset(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> EquipmentAsset:
    asset_number = _clean(values.get("asset_number"), required=True)
    name = _clean(values.get("name"), required=True)
    duplicate = await db.scalar(
        select(EquipmentAsset.id).where(
            EquipmentAsset.organization_id == organization_id,
            EquipmentAsset.asset_number == asset_number,
        )
    )
    if duplicate is not None:
        raise EquipmentConflictError("Equipment asset number already exists")
    payload = dict(values)
    payload["asset_number"] = asset_number
    payload["name"] = name
    payload.pop("organization_id", None)
    asset = EquipmentAsset(organization_id=organization_id, **payload)
    db.add(asset)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.asset.created",
        target_type="equipment_asset",
        target_id=str(asset.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"asset_number": asset.asset_number, "status": asset.status.value},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=None,
        event_type="equipment.asset.changed",
        entity_type="equipment_asset",
        entity_id=asset.id,
        revision=asset.revision,
        permission="equipment.asset.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return asset


async def update_equipment_asset(
    db: AsyncSession,
    *,
    organization_id: UUID,
    asset_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> EquipmentAsset:
    asset = await _require_asset(db, organization_id, asset_id, lock=True)
    if asset.revision != expected_revision:
        raise EquipmentConflictError("Equipment asset was changed by another user")
    allowed = {
        "asset_number",
        "name",
        "category",
        "make",
        "model",
        "serial_number",
        "ownership",
        "status",
        "meter_unit",
        "current_meter",
        "notes",
    }
    filtered = {key: value for key, value in changes.items() if key in allowed}
    if "asset_number" in filtered:
        filtered["asset_number"] = _clean(filtered["asset_number"], required=True)
        duplicate = await db.scalar(
            select(EquipmentAsset.id).where(
                EquipmentAsset.organization_id == organization_id,
                EquipmentAsset.asset_number == filtered["asset_number"],
                EquipmentAsset.id != asset.id,
            )
        )
        if duplicate is not None:
            raise EquipmentConflictError("Equipment asset number already exists")
    if "name" in filtered:
        filtered["name"] = _clean(filtered["name"], required=True)
    previous = {key: getattr(asset, key) for key in filtered}
    for key, value in filtered.items():
        setattr(asset, key, value)
    asset.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.asset.updated",
        target_type="equipment_asset",
        target_id=str(asset.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH if "status" in filtered else AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": previous, "after": filtered, "revision": asset.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=None,
        event_type="equipment.asset.changed",
        entity_type="equipment_asset",
        entity_id=asset.id,
        revision=asset.revision,
        permission="equipment.asset.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return asset


async def assign_equipment_to_project(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> ProjectEquipmentAssignment:
    await _require_project(db, organization_id, project_id)
    asset_id = values.get("equipment_asset_id")
    if not isinstance(asset_id, UUID):
        raise EquipmentValidationError("equipment_asset_id is required")
    asset = await _require_asset(db, organization_id, asset_id, lock=True)
    if asset.status == EquipmentStatus.RETIRED:
        raise EquipmentValidationError("Retired equipment cannot be assigned")
    active = await db.scalar(
        select(ProjectEquipmentAssignment.id).where(
            ProjectEquipmentAssignment.organization_id == organization_id,
            ProjectEquipmentAssignment.equipment_asset_id == asset.id,
            ProjectEquipmentAssignment.status == EquipmentAssignmentStatus.ACTIVE,
        )
    )
    if active is not None:
        raise EquipmentConflictError("Equipment is already actively assigned")
    operator_worker_id = values.get("operator_worker_id")
    if isinstance(operator_worker_id, UUID):
        worker = await db.scalar(
            select(Worker.id).where(
                Worker.id == operator_worker_id,
                Worker.organization_id == organization_id,
            )
        )
        if worker is None:
            raise EquipmentValidationError("Operator Worker was not found")
    payload = dict(values)
    payload.pop("organization_id", None)
    payload.pop("project_id", None)
    assignment = ProjectEquipmentAssignment(
        organization_id=organization_id,
        project_id=project_id,
        **payload,
    )
    db.add(assignment)
    asset.status = EquipmentStatus.ASSIGNED
    asset.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.assignment.created",
        target_type="equipment_assignment",
        target_id=str(assignment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "equipment_asset_id": str(asset.id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="equipment.assignment.changed",
        entity_type="equipment_assignment",
        entity_id=assignment.id,
        revision=assignment.revision,
        permission="equipment.assignment.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return assignment


async def end_equipment_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    expected_revision: int,
    end_date: date,
    ending_meter: Decimal | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectEquipmentAssignment:
    assignment = await db.scalar(
        select(ProjectEquipmentAssignment)
        .where(
            ProjectEquipmentAssignment.id == assignment_id,
            ProjectEquipmentAssignment.organization_id == organization_id,
            ProjectEquipmentAssignment.project_id == project_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise EquipmentValidationError("Equipment assignment was not found")
    if assignment.revision != expected_revision:
        raise EquipmentConflictError("Equipment assignment was changed by another user")
    if assignment.status != EquipmentAssignmentStatus.ACTIVE:
        raise EquipmentValidationError("Only active assignments can be ended")
    if assignment.start_date and end_date < assignment.start_date:
        raise EquipmentValidationError("End date cannot be before start date")
    assignment.status = EquipmentAssignmentStatus.ENDED
    assignment.end_date = end_date
    assignment.ending_meter = ending_meter
    assignment.revision += 1
    asset = await _require_asset(db, organization_id, assignment.equipment_asset_id, lock=True)
    if ending_meter is not None:
        asset.current_meter = ending_meter
    if asset.status == EquipmentStatus.ASSIGNED:
        asset.status = EquipmentStatus.AVAILABLE
    asset.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.assignment.ended",
        target_type="equipment_assignment",
        target_id=str(assignment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"end_date": end_date, "ending_meter": ending_meter},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="equipment.assignment.changed",
        entity_type="equipment_assignment",
        entity_id=assignment.id,
        revision=assignment.revision,
        permission="equipment.assignment.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return assignment


async def create_maintenance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> EquipmentMaintenance:
    asset_id = values.get("equipment_asset_id")
    if not isinstance(asset_id, UUID):
        raise EquipmentValidationError("equipment_asset_id is required")
    await _require_asset(db, organization_id, asset_id)
    project_id = values.get("project_id")
    if isinstance(project_id, UUID):
        await _require_project(db, organization_id, project_id)
    payload = dict(values)
    payload.pop("organization_id", None)
    record = EquipmentMaintenance(organization_id=organization_id, **payload)
    db.add(record)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.maintenance.created",
        target_type="equipment_maintenance",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"equipment_asset_id": str(asset_id), "status": record.status.value},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id if isinstance(project_id, UUID) else None,
        event_type="equipment.maintenance.changed",
        entity_type="equipment_maintenance",
        entity_id=record.id,
        revision=record.revision,
        permission="equipment.maintenance.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return record


async def update_maintenance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    maintenance_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> EquipmentMaintenance:
    record = await db.scalar(
        select(EquipmentMaintenance)
        .where(
            EquipmentMaintenance.id == maintenance_id,
            EquipmentMaintenance.organization_id == organization_id,
        )
        .with_for_update()
    )
    if record is None:
        raise EquipmentValidationError("Maintenance record was not found")
    if record.revision != expected_revision:
        raise EquipmentConflictError("Maintenance record was changed by another user")
    allowed = {
        "status",
        "description",
        "due_date",
        "meter_value",
        "meter_unit",
        "provider",
        "service_reference",
    }
    filtered = {key: value for key, value in changes.items() if key in allowed}
    previous_status = record.status
    for key, value in filtered.items():
        setattr(record, key, value)
    now = datetime.now(UTC)
    if record.status == MaintenanceStatus.IN_PROGRESS and previous_status != record.status:
        record.started_at = record.started_at or now
    if record.status == MaintenanceStatus.COMPLETED and previous_status != record.status:
        record.completed_at = now
        asset = await _require_asset(db, organization_id, record.equipment_asset_id, lock=True)
        if record.meter_value is not None:
            asset.current_meter = record.meter_value
        if asset.status == EquipmentStatus.MAINTENANCE:
            asset.status = EquipmentStatus.AVAILABLE
        asset.revision += 1
    record.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="equipment.maintenance.updated",
        target_type="equipment_maintenance",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"status": record.status.value, "revision": record.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=record.project_id,
        event_type="equipment.maintenance.changed",
        entity_type="equipment_maintenance",
        entity_id=record.id,
        revision=record.revision,
        permission="equipment.maintenance.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return record


async def create_material(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> Material:
    code = _clean(values.get("code"), required=True)
    name = _clean(values.get("name"), required=True)
    duplicate = await db.scalar(
        select(Material.id).where(Material.organization_id == organization_id, Material.code == code)
    )
    if duplicate is not None:
        raise EquipmentConflictError("Material code already exists")
    payload = dict(values)
    payload["code"] = code
    payload["name"] = name
    payload.pop("organization_id", None)
    material = Material(organization_id=organization_id, **payload)
    db.add(material)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.material.created",
        target_type="material",
        target_id=str(material.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"code": material.code, "name": material.name},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=None,
        event_type="materials.material.changed",
        entity_type="material",
        entity_id=material.id,
        revision=material.revision,
        permission="materials.material.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return material


async def update_material(
    db: AsyncSession,
    *,
    organization_id: UUID,
    material_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Material:
    material = await _require_material(db, organization_id, material_id, lock=True)
    if material.revision != expected_revision:
        raise EquipmentConflictError("Material was changed by another user")
    allowed = {"code", "name", "category", "default_unit_code", "description", "status"}
    filtered = {key: value for key, value in changes.items() if key in allowed}
    if "code" in filtered:
        filtered["code"] = _clean(filtered["code"], required=True)
        duplicate = await db.scalar(
            select(Material.id).where(
                Material.organization_id == organization_id,
                Material.code == filtered["code"],
                Material.id != material.id,
            )
        )
        if duplicate is not None:
            raise EquipmentConflictError("Material code already exists")
    if "name" in filtered:
        filtered["name"] = _clean(filtered["name"], required=True)
    for key, value in filtered.items():
        setattr(material, key, value)
    material.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.material.updated",
        target_type="material",
        target_id=str(material.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"after": filtered, "revision": material.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=None,
        event_type="materials.material.changed",
        entity_type="material",
        entity_id=material.id,
        revision=material.revision,
        permission="materials.material.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return material


async def upsert_material_plan(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> ProjectMaterialPlan:
    await _require_project(db, organization_id, project_id)
    material_id = values.get("material_id")
    if not isinstance(material_id, UUID):
        raise EquipmentValidationError("material_id is required")
    await _require_material(db, organization_id, material_id)
    existing = await db.scalar(
        select(ProjectMaterialPlan)
        .where(
            ProjectMaterialPlan.organization_id == organization_id,
            ProjectMaterialPlan.project_id == project_id,
            ProjectMaterialPlan.material_id == material_id,
        )
        .with_for_update()
    )
    expected = values.get("expected_revision")
    if existing is not None and expected is not None and existing.revision != expected:
        raise EquipmentConflictError("Material plan was changed by another user")
    if existing is None:
        existing = ProjectMaterialPlan(
            organization_id=organization_id,
            project_id=project_id,
            material_id=material_id,
            planned_quantity=Decimal(str(values.get("planned_quantity", 0))),
            unit_code=str(values.get("unit_code", "")).strip(),
            notes=values.get("notes"),
        )
        if not existing.unit_code:
            raise EquipmentValidationError("unit_code is required")
        db.add(existing)
    else:
        existing.planned_quantity = Decimal(str(values.get("planned_quantity", existing.planned_quantity)))
        existing.unit_code = str(values.get("unit_code", existing.unit_code)).strip()
        existing.notes = values.get("notes")
        existing.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.plan.changed",
        target_type="project_material_plan",
        target_id=str(existing.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "revision": existing.revision},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="materials.plan.changed",
        entity_type="project_material_plan",
        entity_id=existing.id,
        entity_version=existing.revision,
        required_permission_key="materials.plan.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"id": str(existing.id), "revision": existing.revision},
    )
    return existing


async def create_material_delivery(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> MaterialDelivery:
    await _require_project(db, organization_id, project_id)
    await _require_project_membership(db, organization_id, project_id, membership_id)
    material_id = values.get("material_id")
    if not isinstance(material_id, UUID):
        raise EquipmentValidationError("material_id is required")
    await _require_material(db, organization_id, material_id)
    payload = dict(values)
    payload.pop("organization_id", None)
    payload.pop("project_id", None)
    if payload.get("status") == MaterialDeliveryStatus.RECEIVED:
        payload["received_by_membership_id"] = membership_id
    delivery = MaterialDelivery(
        organization_id=organization_id,
        project_id=project_id,
        **payload,
    )
    db.add(delivery)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.delivery.created",
        target_type="material_delivery",
        target_id=str(delivery.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "status": delivery.status.value},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="materials.delivery.changed",
        entity_type="material_delivery",
        entity_id=delivery.id,
        revision=delivery.revision,
        permission="materials.delivery.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return delivery


async def update_material_delivery(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    delivery_id: UUID,
    expected_revision: int,
    changes: dict[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MaterialDelivery:
    await _require_project_membership(db, organization_id, project_id, membership_id)
    delivery = await db.scalar(
        select(MaterialDelivery)
        .where(
            MaterialDelivery.id == delivery_id,
            MaterialDelivery.organization_id == organization_id,
            MaterialDelivery.project_id == project_id,
        )
        .with_for_update()
    )
    if delivery is None:
        raise EquipmentValidationError("Material delivery was not found")
    if delivery.revision != expected_revision:
        raise EquipmentConflictError("Material delivery was changed by another user")
    if delivery.status in {MaterialDeliveryStatus.REJECTED, MaterialDeliveryStatus.CANCELLED}:
        raise EquipmentValidationError("Rejected or cancelled deliveries cannot be edited")
    allowed = {
        "status",
        "quantity",
        "unit_code",
        "supplier",
        "ticket_number",
        "delivered_at",
        "location",
        "notes",
    }
    filtered = {key: value for key, value in changes.items() if key in allowed}
    for key, value in filtered.items():
        setattr(delivery, key, value)
    if delivery.status == MaterialDeliveryStatus.RECEIVED:
        delivery.received_by_membership_id = membership_id
    delivery.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.delivery.updated",
        target_type="material_delivery",
        target_id=str(delivery.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"after": filtered, "revision": delivery.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="materials.delivery.changed",
        entity_type="material_delivery",
        entity_id=delivery.id,
        revision=delivery.revision,
        permission="materials.delivery.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return delivery
