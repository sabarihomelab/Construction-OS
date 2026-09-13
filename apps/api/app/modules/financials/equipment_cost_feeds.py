from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.equipment.models import EquipmentAsset, ProjectEquipmentAssignment
from app.modules.equipment.usage_models import (
    EquipmentRateBasis,
    EquipmentUsage,
    EquipmentUsageStatus,
    ProjectEquipmentRate,
)
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


def _usage_cost(usage: EquipmentUsage, rate: ProjectEquipmentRate) -> Decimal:
    if rate.rate_basis != EquipmentRateBasis.HOURLY:
        raise FinancialValidationError(
            "Automatic equipment job cost currently supports hourly equipment rates only"
        )
    if usage.operating_hours is None or usage.operating_hours <= 0:
        raise FinancialValidationError(
            "Positive operating_hours are required for hourly equipment cost posting"
        )
    if rate.rate <= 0:
        raise FinancialValidationError(
            "Equipment hourly rate must be positive before job-cost posting"
        )
    return (usage.operating_hours * rate.rate).quantize(Decimal("0.01"))


async def _effective_rate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    assignment_id: UUID,
    usage_date,
) -> ProjectEquipmentRate:
    rows = list(
        (
            await db.scalars(
                select(ProjectEquipmentRate)
                .where(
                    ProjectEquipmentRate.organization_id == organization_id,
                    ProjectEquipmentRate.project_id == project_id,
                    ProjectEquipmentRate.equipment_assignment_id == assignment_id,
                    ProjectEquipmentRate.effective_from <= usage_date,
                    or_(
                        ProjectEquipmentRate.effective_to.is_(None),
                        ProjectEquipmentRate.effective_to >= usage_date,
                    ),
                )
                .order_by(ProjectEquipmentRate.effective_from.desc())
            )
        ).all()
    )
    if not rows:
        raise FinancialValidationError(
            "No effective equipment cost rate exists for this usage date"
        )
    if len(rows) > 1:
        raise FinancialConflictError(
            "Multiple equipment cost rates are effective on this usage date"
        )
    return rows[0]


async def post_equipment_usage_cost(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    usage_id: UUID,
    equipment_cost_head_id: UUID,
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
            ProjectCostEntry.source_type == ProjectCostSourceType.EQUIPMENT_USAGE,
            ProjectCostEntry.source_id == usage_id,
        )
    )
    if existing is not None:
        if existing.status == ProjectCostStatus.POSTED:
            return existing
        raise FinancialConflictError(
            "This equipment usage already has a non-posted project cost record"
        )

    usage = await db.scalar(
        select(EquipmentUsage).where(
            EquipmentUsage.id == usage_id,
            EquipmentUsage.organization_id == organization_id,
            EquipmentUsage.project_id == project_id,
        )
    )
    if usage is None:
        raise FinancialValidationError("Equipment usage was not found in this project")
    if usage.status != EquipmentUsageStatus.POSTED:
        raise FinancialValidationError(
            "Only posted equipment usage can become project equipment cost"
        )

    assignment = await db.scalar(
        select(ProjectEquipmentAssignment).where(
            ProjectEquipmentAssignment.id == usage.equipment_assignment_id,
            ProjectEquipmentAssignment.organization_id == organization_id,
            ProjectEquipmentAssignment.project_id == project_id,
        )
    )
    if assignment is None:
        raise FinancialValidationError(
            "Equipment assignment was not found in this project"
        )
    asset = await db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.id == assignment.equipment_asset_id,
            EquipmentAsset.organization_id == organization_id,
        )
    )
    if asset is None:
        raise FinancialValidationError("Equipment asset was not found")

    rate = await _effective_rate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        assignment_id=assignment.id,
        usage_date=usage.usage_date,
    )
    project_currency = (project.currency_code or "INR").upper()
    if rate.currency_code.upper() != project_currency:
        raise FinancialValidationError(
            "Equipment rate currency must match project currency before cost posting"
        )
    amount = _usage_cost(usage, rate)

    cost_head = await db.scalar(
        select(CostHead).where(
            CostHead.id == equipment_cost_head_id,
            CostHead.organization_id == organization_id,
        )
    )
    if (
        cost_head is None
        or cost_head.status != RecordStatus.ACTIVE
        or not cost_head.allows_posting
        or cost_head.category != CostHeadCategory.EQUIPMENT
    ):
        raise FinancialValidationError(
            "Equipment costing requires an active posting Equipment Cost Head"
        )

    entry_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="project_cost",
        prefix="COST",
    )
    now = datetime.now(UTC)
    source_reference = usage.source_reference or f"Equipment usage {usage.id}"
    cost_entry = ProjectCostEntry(
        organization_id=organization_id,
        project_id=project_id,
        entry_number=entry_number,
        entry_date=usage.usage_date,
        source_type=ProjectCostSourceType.EQUIPMENT_USAGE,
        source_id=usage.id,
        source_reference=source_reference,
        description=f"Equipment usage · {asset.asset_number} · {asset.name}",
        total_amount=amount,
        currency_code=project_currency,
        status=ProjectCostStatus.POSTED,
        configuration_context={
            "equipment_usage_id": str(usage.id),
            "equipment_usage_revision": usage.revision,
            "equipment_assignment_id": str(assignment.id),
            "equipment_asset_id": str(asset.id),
            "equipment_cost_head_id": str(cost_head.id),
            "equipment_rate_id": str(rate.id),
            "equipment_rate_revision": rate.revision,
            "rate_basis": rate.rate_basis.value,
            "rate": str(rate.rate),
            "operating_hours": str(usage.operating_hours),
            "currency_code": rate.currency_code,
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
            wbs_code_id=usage.wbs_code_id,
            boq_item_id=usage.boq_item_id,
            equipment_asset_id=asset.id,
            description=f"Used {asset.name}",
            quantity=usage.operating_hours,
            unit_code="hour",
            amount=amount,
        )
    )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.project_cost.equipment.posted",
        target_type="project_cost_entry",
        target_id=str(cost_entry.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "equipment_usage_id": str(usage.id),
            "equipment_asset_id": str(asset.id),
            "equipment_rate_id": str(rate.id),
            "amount": amount,
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
            "source_type": ProjectCostSourceType.EQUIPMENT_USAGE.value,
            "source_id": str(usage.id),
            "equipment_asset_id": str(asset.id),
            "amount": str(amount),
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
