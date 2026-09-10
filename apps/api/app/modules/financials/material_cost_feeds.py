from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.equipment.consumption_models import (
    MaterialConsumption,
    MaterialConsumptionStatus,
)
from app.modules.equipment.models import Material
from app.modules.events.service import enqueue_event
from app.modules.financials.job_cost_models import (
    CostHead,
    CostHeadCategory,
    ProjectCostAllocation,
    ProjectCostEntry,
    ProjectCostSourceType,
    ProjectCostStatus,
)
from app.modules.financials.models import RecordStatus
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    _next_project_number,
    _require_project,
    _require_project_membership,
)
from app.modules.search.service import schedule_search_index


async def post_material_consumption_cost(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    consumption_id: UUID,
    material_cost_head_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectCostEntry:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    project = await _require_project(db, organization_id, project_id)

    existing = await db.scalar(
        select(ProjectCostEntry).where(
            ProjectCostEntry.organization_id == organization_id,
            ProjectCostEntry.project_id == project_id,
            ProjectCostEntry.source_type == ProjectCostSourceType.MATERIAL_CONSUMPTION,
            ProjectCostEntry.source_id == consumption_id,
        )
    )
    if existing is not None:
        if existing.status == ProjectCostStatus.POSTED:
            return existing
        raise FinancialConflictError(
            "This material consumption already has a non-posted project cost record"
        )

    consumption = await db.scalar(
        select(MaterialConsumption).where(
            MaterialConsumption.id == consumption_id,
            MaterialConsumption.organization_id == organization_id,
            MaterialConsumption.project_id == project_id,
        )
    )
    if consumption is None:
        raise FinancialValidationError("Material consumption was not found in this project")
    if consumption.status != MaterialConsumptionStatus.POSTED:
        raise FinancialValidationError(
            "Only a posted material consumption can become project material cost"
        )
    if consumption.unit_cost is None or consumption.total_cost is None:
        raise FinancialValidationError(
            "Posted material consumption is missing its governed cost snapshot"
        )
    if consumption.total_cost <= Decimal(0):
        raise FinancialValidationError(
            "Material consumption must have a positive total cost before financial posting"
        )

    project_currency = (project.currency_code or "INR").upper()
    if consumption.currency_code.upper() != project_currency:
        raise FinancialValidationError(
            "Material consumption currency must match project currency before cost posting"
        )

    cost_head = await db.scalar(
        select(CostHead).where(
            CostHead.id == material_cost_head_id,
            CostHead.organization_id == organization_id,
        )
    )
    if (
        cost_head is None
        or cost_head.status != RecordStatus.ACTIVE
        or not cost_head.allows_posting
        or cost_head.category != CostHeadCategory.MATERIAL
    ):
        raise FinancialValidationError(
            "Material costing requires an active posting Material Cost Head"
        )

    material = await db.scalar(
        select(Material).where(
            Material.id == consumption.material_id,
            Material.organization_id == organization_id,
        )
    )
    if material is None:
        raise FinancialValidationError("Material master was not found")

    entry_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="project_cost",
        prefix="COST",
    )
    now = datetime.now(UTC)
    source_reference = consumption.source_reference or f"Material consumption {consumption.id}"
    cost_entry = ProjectCostEntry(
        organization_id=organization_id,
        project_id=project_id,
        entry_number=entry_number,
        entry_date=consumption.consumption_date,
        source_type=ProjectCostSourceType.MATERIAL_CONSUMPTION,
        source_id=consumption.id,
        source_reference=source_reference,
        description=f"Material consumption · {material.code} · {material.name}",
        total_amount=consumption.total_cost,
        currency_code=project_currency,
        status=ProjectCostStatus.POSTED,
        configuration_context={
            "material_consumption_id": str(consumption.id),
            "material_consumption_revision": consumption.revision,
            "material_id": str(consumption.material_id),
            "material_cost_head_id": str(cost_head.id),
            "quantity": str(consumption.quantity),
            "unit_code": consumption.unit_code,
            "unit_cost": str(consumption.unit_cost),
            "total_cost": str(consumption.total_cost),
            "cost_basis": consumption.cost_basis,
            "currency_code": consumption.currency_code,
        },
        revision=1,
        posted_by_membership_id=membership_id,
        posted_at=now,
    )
    db.add(cost_entry)
    await db.flush()

    db.add(
        ProjectCostAllocation(
            organization_id=organization_id,
            project_id=project_id,
            cost_entry_id=cost_entry.id,
            line_number=1,
            cost_head_id=cost_head.id,
            wbs_code_id=consumption.wbs_code_id,
            boq_item_id=consumption.boq_item_id,
            material_id=consumption.material_id,
            description=f"Consumed {material.name}",
            quantity=consumption.quantity,
            unit_code=consumption.unit_code,
            amount=consumption.total_cost,
        )
    )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.project_cost.material.posted",
        target_type="project_cost_entry",
        target_id=str(cost_entry.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "material_consumption_id": str(consumption.id),
            "material_id": str(consumption.material_id),
            "amount": consumption.total_cost,
            "currency_code": project_currency,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.project_cost.posted",
        entity_type="project_cost_entry",
        entity_id=cost_entry.id,
        entity_version=cost_entry.revision,
        required_permission_key="financials.project_cost.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "source_type": ProjectCostSourceType.MATERIAL_CONSUMPTION.value,
            "source_id": str(consumption.id),
            "material_id": str(consumption.material_id),
            "amount": str(consumption.total_cost),
        },
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="project_cost_entry",
        entity_id=cost_entry.id,
        entity_version=cost_entry.revision,
    )
    return cost_entry
