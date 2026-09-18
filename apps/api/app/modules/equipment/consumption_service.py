from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQItem, WBSCode
from app.modules.equipment.consumption_models import (
    MaterialConsumption,
    MaterialConsumptionStatus,
)
from app.modules.equipment.inventory_service import (
    InventoryValidationError,
    record_material_consumption_stock,
    require_stock_location,
)
from app.modules.equipment.models import Material, MaterialStatus
from app.modules.events.service import enqueue_event
from app.modules.projects.models import (
    Project,
    ProjectMembership,
    ProjectMembershipStatus,
)


class MaterialConsumptionValidationError(ValueError):
    pass


class MaterialConsumptionConflictError(MaterialConsumptionValidationError):
    pass


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def _project_for_scope(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> Project:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise MaterialConsumptionValidationError("Project was not found")
    return project


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    found = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if found is None:
        raise MaterialConsumptionValidationError(
            "Active project membership is required for material consumption"
        )


async def _validate_references(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    material_id: UUID,
    unit_code: str,
    wbs_code_id: UUID | None,
    boq_item_id: UUID | None,
) -> Material:
    material = await db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.organization_id == organization_id,
        )
    )
    if material is None or material.status != MaterialStatus.ACTIVE:
        raise MaterialConsumptionValidationError("An active company Material is required")

    normalized_unit = unit_code.strip()
    if not normalized_unit:
        raise MaterialConsumptionValidationError("unit_code is required")
    if normalized_unit.casefold() != material.default_unit_code.strip().casefold():
        raise MaterialConsumptionValidationError(
            "Material consumption unit must match the Material default unit until a governed UOM conversion is configured"
        )

    if wbs_code_id is not None:
        wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_code_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if wbs is None:
            raise MaterialConsumptionValidationError(
                "WBS/Cost Code was not found in this project"
            )

    if boq_item_id is not None:
        boq_item = await db.scalar(
            select(BOQItem.id).where(
                BOQItem.id == boq_item_id,
                BOQItem.organization_id == organization_id,
                BOQItem.project_id == project_id,
            )
        )
        if boq_item is None:
            raise MaterialConsumptionValidationError("BOQ item was not found in this project")

    return material


async def create_material_consumption(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: dict[str, object],
    session_id: UUID | None = None,
) -> MaterialConsumption:
    project = await _project_for_scope(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )

    material_id = values.get("material_id")
    if not isinstance(material_id, UUID):
        raise MaterialConsumptionValidationError("material_id is required")
    stock_location_id = values.get("stock_location_id")
    if not isinstance(stock_location_id, UUID):
        raise MaterialConsumptionValidationError("stock_location_id is required")
    try:
        await require_stock_location(
            db,
            organization_id=organization_id,
            project_id=project_id,
            stock_location_id=stock_location_id,
        )
    except InventoryValidationError as exc:
        raise MaterialConsumptionValidationError(str(exc)) from exc

    unit_code = str(values.get("unit_code") or "").strip()
    wbs_code_id = values.get("wbs_code_id")
    boq_item_id = values.get("boq_item_id")
    await _validate_references(
        db,
        organization_id=organization_id,
        project_id=project_id,
        material_id=material_id,
        unit_code=unit_code,
        wbs_code_id=wbs_code_id if isinstance(wbs_code_id, UUID) else None,
        boq_item_id=boq_item_id if isinstance(boq_item_id, UUID) else None,
    )

    payload = dict(values)
    payload.pop("organization_id", None)
    payload.pop("project_id", None)
    payload.pop("currency_code", None)
    payload.pop("status", None)
    payload.pop("total_cost", None)
    payload["unit_code"] = unit_code
    record = MaterialConsumption(
        organization_id=organization_id,
        project_id=project_id,
        currency_code=(project.currency_code or "INR").upper(),
        status=MaterialConsumptionStatus.DRAFT,
        created_by_membership_id=membership_id,
        **payload,
    )
    db.add(record)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.consumption.created",
        target_type="material_consumption",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "project_id": str(project_id),
            "material_id": str(material_id),
            "stock_location_id": str(stock_location_id),
            "quantity": record.quantity,
            "unit_code": record.unit_code,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="materials.consumption.changed",
        entity_type="material_consumption",
        entity_id=record.id,
        entity_version=record.revision,
        required_permission_key="materials.consumption.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"status": record.status.value},
    )
    return record


async def post_material_consumption(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    consumption_id: UUID,
    membership_id: UUID,
    expected_revision: int,
    unit_cost: Decimal | None,
    cost_basis: str | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MaterialConsumption:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    record = await db.scalar(
        select(MaterialConsumption)
        .where(
            MaterialConsumption.id == consumption_id,
            MaterialConsumption.organization_id == organization_id,
            MaterialConsumption.project_id == project_id,
        )
        .with_for_update()
    )
    if record is None:
        raise MaterialConsumptionValidationError("Material consumption was not found")
    if record.revision != expected_revision:
        raise MaterialConsumptionConflictError(
            "Material consumption was changed by another user"
        )
    if record.status != MaterialConsumptionStatus.DRAFT:
        raise MaterialConsumptionValidationError(
            "Only a draft material consumption can be posted"
        )
    if record.stock_location_id is None:
        raise MaterialConsumptionValidationError(
            "A stock location is required before material consumption can be posted"
        )

    await _validate_references(
        db,
        organization_id=organization_id,
        project_id=project_id,
        material_id=record.material_id,
        unit_code=record.unit_code,
        wbs_code_id=record.wbs_code_id,
        boq_item_id=record.boq_item_id,
    )

    if unit_cost is not None:
        record.unit_cost = unit_cost
    if cost_basis is not None:
        record.cost_basis = cost_basis.strip() or None
    if record.unit_cost is None:
        raise MaterialConsumptionValidationError(
            "A governed material unit cost is required before consumption can be posted"
        )

    record.total_cost = _money(record.quantity * record.unit_cost)
    try:
        await record_material_consumption_stock(
            db,
            organization_id=organization_id,
            project_id=project_id,
            stock_location_id=record.stock_location_id,
            material_id=record.material_id,
            wbs_code_id=record.wbs_code_id,
            boq_item_id=record.boq_item_id,
            quantity=record.quantity,
            unit_code=record.unit_code,
            consumption_date=record.consumption_date,
            consumption_id=record.id,
            source_reference=record.source_reference,
            unit_cost_snapshot=record.unit_cost,
            currency_code=record.currency_code,
            membership_id=membership_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    except InventoryValidationError as exc:
        raise MaterialConsumptionValidationError(str(exc)) from exc

    record.status = MaterialConsumptionStatus.POSTED
    record.posted_by_membership_id = membership_id
    record.posted_at = datetime.now(UTC)
    record.revision += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="materials.consumption.posted",
        target_type="material_consumption",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "project_id": str(project_id),
            "material_id": str(record.material_id),
            "stock_location_id": str(record.stock_location_id),
            "quantity": record.quantity,
            "unit_cost": record.unit_cost,
            "total_cost": record.total_cost,
            "currency_code": record.currency_code,
            "cost_basis": record.cost_basis,
            "revision": record.revision,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="materials.consumption.posted",
        entity_type="material_consumption",
        entity_id=record.id,
        entity_version=record.revision,
        required_permission_key="materials.consumption.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "material_id": str(record.material_id),
            "stock_location_id": str(record.stock_location_id),
            "quantity": str(record.quantity),
            "total_cost": str(record.total_cost),
            "currency_code": record.currency_code,
        },
    )
    return record
