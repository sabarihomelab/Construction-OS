from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQ, BOQItem, WBSCode
from app.modules.estimating.models import (
    BudgetCategory,
    BudgetLine,
    BudgetStatus,
    EstimateItem,
    EstimateStatus,
    ProjectBudget,
    ProjectEstimate,
    RateAnalysis,
    RateAnalysisComponent,
    RateComponentKind,
)
from app.modules.events.service import enqueue_event
from app.modules.identity.models import MembershipStatus, OrganizationMembership
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.search.service import schedule_search_index


class EstimatingValidationError(ValueError):
    pass


class EstimatingConflictError(ValueError):
    pass


MONEY = Decimal("0.01")
HUNDRED = Decimal(100)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> Project:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise EstimatingValidationError("Project was not found")
    return project


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    member = await db.scalar(
        select(OrganizationMembership.id)
        .join(
            ProjectMembership,
            (ProjectMembership.organization_membership_id == OrganizationMembership.id)
            & (ProjectMembership.organization_id == OrganizationMembership.organization_id),
        )
        .where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            ProjectMembership.project_id == project_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if member is None:
        raise EstimatingValidationError("Approver must be an active member of this project")


async def _publish(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    entity_version: int,
    permission: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key=permission,
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": entity_version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
    )


async def create_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectEstimate:
    await _require_project(db, organization_id, project_id)
    data = dict(values)
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise EstimatingValidationError("Estimate code and name are required")
    duplicate = await db.scalar(
        select(ProjectEstimate.id).where(
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.code == code,
        )
    )
    if duplicate is not None:
        raise EstimatingConflictError("Estimate code already exists in this project")
    source_boq_id = data.get("source_boq_id")
    if isinstance(source_boq_id, UUID):
        boq = await db.scalar(
            select(BOQ).where(
                BOQ.id == source_boq_id,
                BOQ.project_id == project_id,
                BOQ.organization_id == organization_id,
            )
        )
        if boq is None:
            raise EstimatingValidationError("Source BOQ was not found in this project")
    data["code"] = code
    data["name"] = name
    data["currency_code"] = str(data.get("currency_code") or "INR").upper()
    estimate = ProjectEstimate(organization_id=organization_id, project_id=project_id, **data)
    db.add(estimate)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.estimate.created",
        target_type="project_estimate",
        target_id=str(estimate.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"code": estimate.code, "project_id": str(project_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.estimate.created",
        entity_type="project_estimate",
        entity_id=estimate.id,
        entity_version=estimate.revision,
        permission="estimating.estimate.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return estimate


async def add_estimate_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> EstimateItem:
    estimate = await db.scalar(
        select(ProjectEstimate)
        .where(
            ProjectEstimate.id == estimate_id,
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.organization_id == organization_id,
        )
        .with_for_update()
    )
    if estimate is None:
        raise EstimatingValidationError("Estimate was not found")
    if estimate.status != EstimateStatus.DRAFT:
        raise EstimatingValidationError("Only draft estimates can be edited")
    data = dict(values)
    wbs_id = data.get("wbs_code_id")
    if isinstance(wbs_id, UUID):
        wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_id,
                WBSCode.project_id == project_id,
                WBSCode.organization_id == organization_id,
            )
        )
        if wbs is None:
            raise EstimatingValidationError("WBS code was not found in this project")
    boq_item_id = data.get("boq_item_id")
    if isinstance(boq_item_id, UUID):
        boq_item = await db.scalar(
            select(BOQItem.id).where(
                BOQItem.id == boq_item_id,
                BOQItem.project_id == project_id,
                BOQItem.organization_id == organization_id,
            )
        )
        if boq_item is None:
            raise EstimatingValidationError("BOQ item was not found in this project")
    quantity = Decimal(data.get("quantity") or 0)
    rate = Decimal(data.get("rate") or 0)
    data["quantity"] = quantity
    data["rate"] = money(rate)
    data["amount"] = money(quantity * rate)
    item = EstimateItem(
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
        **data,
    )
    db.add(item)
    estimate.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.item.created",
        target_type="estimate_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"estimate_id": str(estimate_id), "amount": str(item.amount)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.estimate.updated",
        entity_type="project_estimate",
        entity_id=estimate.id,
        entity_version=estimate.revision,
        permission="estimating.estimate.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return item


async def create_rate_analysis(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> RateAnalysis:
    estimate_item_id = values.get("estimate_item_id")
    if not isinstance(estimate_item_id, UUID):
        raise EstimatingValidationError("Estimate item is required")
    item = await db.scalar(
        select(EstimateItem)
        .where(
            EstimateItem.id == estimate_item_id,
            EstimateItem.project_id == project_id,
            EstimateItem.organization_id == organization_id,
        )
        .with_for_update()
    )
    if item is None:
        raise EstimatingValidationError("Estimate item was not found")
    estimate = await db.scalar(
        select(ProjectEstimate).where(
            ProjectEstimate.id == item.estimate_id,
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.organization_id == organization_id,
        )
    )
    if estimate is None or estimate.status != EstimateStatus.DRAFT:
        raise EstimatingValidationError("Rate analysis can only change draft estimates")

    components = list(values.get("components") or [])
    if not components:
        raise EstimatingValidationError("At least one rate component is required")
    current = await db.scalars(
        select(RateAnalysis).where(
            RateAnalysis.estimate_item_id == estimate_item_id,
            RateAnalysis.is_current.is_(True),
        )
    )
    for old in current.all():
        old.is_current = False
    version_number = (
        await db.scalar(
            select(func.coalesce(func.max(RateAnalysis.version_number), 0)).where(
                RateAnalysis.estimate_item_id == estimate_item_id
            )
        )
        or 0
    ) + 1

    base = Decimal(0)
    prepared: list[dict[str, object]] = []
    for raw in components:
        row = dict(raw)
        quantity = Decimal(row.get("quantity") or 0)
        unit_rate = Decimal(row.get("unit_rate") or 0)
        amount = money(quantity * unit_rate)
        row["quantity"] = quantity
        row["unit_rate"] = money(unit_rate)
        row["amount"] = amount
        prepared.append(row)
        base += amount

    wastage = Decimal(values.get("wastage_percent") or 0)
    overhead = Decimal(values.get("overhead_percent") or 0)
    profit = Decimal(values.get("profit_percent") or 0)
    with_wastage = base + (base * wastage / HUNDRED)
    with_overhead = with_wastage + (with_wastage * overhead / HUNDRED)
    calculated_rate = money(with_overhead + (with_overhead * profit / HUNDRED))
    analysis = RateAnalysis(
        organization_id=organization_id,
        project_id=project_id,
        estimate_item_id=estimate_item_id,
        version_number=version_number,
        wastage_percent=wastage,
        overhead_percent=overhead,
        profit_percent=profit,
        calculated_rate=calculated_rate,
        is_current=True,
        notes=values.get("notes") if isinstance(values.get("notes"), str) else None,
    )
    db.add(analysis)
    await db.flush()
    for row in prepared:
        db.add(
            RateAnalysisComponent(
                organization_id=organization_id,
                project_id=project_id,
                analysis_id=analysis.id,
                **row,
            )
        )
    item.rate = calculated_rate
    item.amount = money(item.quantity * calculated_rate)
    item.revision += 1
    estimate.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.rate_analysis.created",
        target_type="rate_analysis",
        target_id=str(analysis.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "estimate_item_id": str(estimate_item_id),
            "version_number": version_number,
            "calculated_rate": str(calculated_rate),
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.estimate.updated",
        entity_type="project_estimate",
        entity_id=estimate.id,
        entity_version=estimate.revision,
        permission="estimating.estimate.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return analysis


async def transition_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    expected_revision: int,
    target: EstimateStatus,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectEstimate:
    estimate = await db.scalar(
        select(ProjectEstimate)
        .where(
            ProjectEstimate.id == estimate_id,
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.organization_id == organization_id,
        )
        .with_for_update()
    )
    if estimate is None:
        raise EstimatingValidationError("Estimate was not found")
    if estimate.revision != expected_revision:
        raise EstimatingConflictError("Estimate changed; refresh before continuing")
    allowed = {
        EstimateStatus.DRAFT: {EstimateStatus.SUBMITTED, EstimateStatus.CANCELLED},
        EstimateStatus.SUBMITTED: {EstimateStatus.DRAFT, EstimateStatus.APPROVED, EstimateStatus.CANCELLED},
        EstimateStatus.APPROVED: {EstimateStatus.SUPERSEDED},
    }
    if target not in allowed.get(estimate.status, set()):
        raise EstimatingValidationError(
            f"Estimate cannot move from {estimate.status.value} to {target.value}"
        )
    if target == EstimateStatus.APPROVED:
        await _require_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=actor_membership_id,
        )
        item_count = await db.scalar(
            select(func.count(EstimateItem.id)).where(EstimateItem.estimate_id == estimate.id)
        )
        if not item_count:
            raise EstimatingValidationError("An estimate with no items cannot be approved")
        estimate.approved_by_membership_id = actor_membership_id
        estimate.approved_at = datetime.now(UTC)
    estimate.status = target
    estimate.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"estimating.estimate.{target.value}",
        target_type="project_estimate",
        target_id=str(estimate.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if target == EstimateStatus.APPROVED else AuditRisk.HIGH,
        reason=reason,
        changes={"status": target.value, "revision": estimate.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"estimating.estimate.{target.value}",
        entity_type="project_estimate",
        entity_id=estimate.id,
        entity_version=estimate.revision,
        permission="estimating.estimate.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return estimate


async def create_budget(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectBudget:
    await _require_project(db, organization_id, project_id)
    data = dict(values)
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise EstimatingValidationError("Budget code and name are required")
    if await db.scalar(
        select(ProjectBudget.id).where(ProjectBudget.project_id == project_id, ProjectBudget.code == code)
    ):
        raise EstimatingConflictError("Budget code already exists in this project")
    estimate_id = data.get("estimate_id")
    if isinstance(estimate_id, UUID):
        estimate = await db.scalar(
            select(ProjectEstimate).where(
                ProjectEstimate.id == estimate_id,
                ProjectEstimate.project_id == project_id,
                ProjectEstimate.organization_id == organization_id,
            )
        )
        if estimate is None:
            raise EstimatingValidationError("Estimate was not found in this project")
    data["code"] = code
    data["name"] = name
    data["currency_code"] = str(data.get("currency_code") or "INR").upper()
    budget = ProjectBudget(organization_id=organization_id, project_id=project_id, **data)
    db.add(budget)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.budget.created",
        target_type="project_budget",
        target_id=str(budget.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"code": budget.code, "project_id": str(project_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.budget.created",
        entity_type="project_budget",
        entity_id=budget.id,
        entity_version=budget.revision,
        permission="estimating.budget.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return budget


async def add_budget_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    budget_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> BudgetLine:
    budget = await db.scalar(
        select(ProjectBudget)
        .where(
            ProjectBudget.id == budget_id,
            ProjectBudget.project_id == project_id,
            ProjectBudget.organization_id == organization_id,
        )
        .with_for_update()
    )
    if budget is None:
        raise EstimatingValidationError("Budget was not found")
    if budget.status != BudgetStatus.DRAFT:
        raise EstimatingValidationError("Only draft budgets can be edited")
    wbs_code_id = values.get("wbs_code_id")
    if not isinstance(wbs_code_id, UUID):
        raise EstimatingValidationError("WBS code is required")
    wbs = await db.scalar(
        select(WBSCode.id).where(
            WBSCode.id == wbs_code_id,
            WBSCode.project_id == project_id,
            WBSCode.organization_id == organization_id,
        )
    )
    if wbs is None:
        raise EstimatingValidationError("WBS code was not found in this project")
    data = dict(values)
    data["amount"] = money(Decimal(data.get("amount") or 0))
    line = BudgetLine(
        organization_id=organization_id,
        project_id=project_id,
        budget_id=budget_id,
        **data,
    )
    db.add(line)
    budget.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.budget_line.created",
        target_type="budget_line",
        target_id=str(line.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"budget_id": str(budget_id), "amount": str(line.amount)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.budget.updated",
        entity_type="project_budget",
        entity_id=budget.id,
        entity_version=budget.revision,
        permission="estimating.budget.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return line


async def create_budget_from_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    code: str,
    name: str,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectBudget:
    estimate = await db.scalar(
        select(ProjectEstimate).where(
            ProjectEstimate.id == estimate_id,
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.organization_id == organization_id,
        )
    )
    if estimate is None or estimate.status != EstimateStatus.APPROVED:
        raise EstimatingValidationError("Budget generation requires an approved estimate")
    budget = await create_budget(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values={
            "code": code,
            "name": name,
            "currency_code": estimate.currency_code,
            "estimate_id": estimate.id,
        },
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    items = list(
        (
            await db.scalars(
                select(EstimateItem).where(EstimateItem.estimate_id == estimate.id)
            )
        ).all()
    )
    grouped: dict[tuple[UUID, BudgetCategory], Decimal] = defaultdict(Decimal)
    kind_map = {
        RateComponentKind.MATERIAL: BudgetCategory.MATERIAL,
        RateComponentKind.LABOUR: BudgetCategory.LABOUR,
        RateComponentKind.EQUIPMENT: BudgetCategory.EQUIPMENT,
        RateComponentKind.SUBCONTRACT: BudgetCategory.SUBCONTRACT,
        RateComponentKind.OVERHEAD: BudgetCategory.OVERHEAD,
        RateComponentKind.OTHER: BudgetCategory.OTHER,
    }
    for item in items:
        if item.wbs_code_id is None:
            continue
        analysis = await db.scalar(
            select(RateAnalysis).where(
                RateAnalysis.estimate_item_id == item.id,
                RateAnalysis.is_current.is_(True),
            )
        )
        if analysis is None:
            grouped[(item.wbs_code_id, BudgetCategory.OTHER)] += item.amount
            continue
        components = list(
            (
                await db.scalars(
                    select(RateAnalysisComponent).where(
                        RateAnalysisComponent.analysis_id == analysis.id
                    )
                )
            ).all()
        )
        if not components:
            grouped[(item.wbs_code_id, BudgetCategory.OTHER)] += item.amount
            continue
        for component in components:
            grouped[(item.wbs_code_id, kind_map[component.kind])] += money(
                component.amount * item.quantity
            )
    for (wbs_id, category), amount in grouped.items():
        await add_budget_line(
            db,
            organization_id=organization_id,
            project_id=project_id,
            budget_id=budget.id,
            values={"wbs_code_id": wbs_id, "category": category, "amount": money(amount)},
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    return budget


async def approve_budget(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    budget_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectBudget:
    budget = await db.scalar(
        select(ProjectBudget)
        .where(
            ProjectBudget.id == budget_id,
            ProjectBudget.project_id == project_id,
            ProjectBudget.organization_id == organization_id,
        )
        .with_for_update()
    )
    if budget is None:
        raise EstimatingValidationError("Budget was not found")
    if budget.revision != expected_revision:
        raise EstimatingConflictError("Budget changed; refresh before approving")
    if budget.status != BudgetStatus.DRAFT:
        raise EstimatingValidationError("Only draft budgets can be approved")
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=actor_membership_id,
    )
    line_count = await db.scalar(
        select(func.count(BudgetLine.id)).where(BudgetLine.budget_id == budget.id)
    )
    if not line_count:
        raise EstimatingValidationError("Budget must contain at least one line")
    budget.status = BudgetStatus.APPROVED
    budget.approved_by_membership_id = actor_membership_id
    budget.approved_at = datetime.now(UTC)
    budget.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.budget.approved",
        target_type="project_budget",
        target_id=str(budget.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"status": budget.status.value, "revision": budget.revision},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.budget.approved",
        entity_type="project_budget",
        entity_id=budget.id,
        entity_version=budget.revision,
        permission="estimating.budget.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return budget
