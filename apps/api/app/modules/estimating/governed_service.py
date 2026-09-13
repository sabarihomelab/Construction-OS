import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQ, BOQItem, BOQStatus, RecordStatus, WBSCode
from app.modules.estimating import service as legacy
from app.modules.estimating.history_models import (
    BudgetApprovalSnapshot,
    EstimateApprovalSnapshot,
    EstimateRevisionLink,
)
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

EstimatingConflictError = legacy.EstimatingConflictError
EstimatingValidationError = legacy.EstimatingValidationError

MONEY = Decimal("0.01")
HUNDRED = Decimal(100)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def rate_breakdown(
    base_rate: Decimal,
    wastage_percent: Decimal,
    overhead_percent: Decimal,
    profit_percent: Decimal,
) -> dict[str, Decimal]:
    base = money(base_rate)
    wastage = money(base * wastage_percent / HUNDRED)
    cost_after_wastage = money(base + wastage)
    overhead = money(cost_after_wastage * overhead_percent / HUNDRED)
    cost_rate = money(cost_after_wastage + overhead)
    profit = money(cost_rate * profit_percent / HUNDRED)
    selling_rate = money(cost_rate + profit)
    return {
        "base_rate": base,
        "wastage_amount": wastage,
        "overhead_amount": overhead,
        "cost_rate": cost_rate,
        "profit_amount": profit,
        "selling_rate": selling_rate,
    }


async def _load_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    for_update: bool = False,
) -> ProjectEstimate:
    statement = select(ProjectEstimate).where(
        ProjectEstimate.id == estimate_id,
        ProjectEstimate.organization_id == organization_id,
        ProjectEstimate.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    row = await db.scalar(statement)
    if row is None:
        raise EstimatingValidationError("Estimate was not found")
    return row


async def _load_budget(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    budget_id: UUID,
    for_update: bool = False,
) -> ProjectBudget:
    statement = select(ProjectBudget).where(
        ProjectBudget.id == budget_id,
        ProjectBudget.organization_id == organization_id,
        ProjectBudget.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    row = await db.scalar(statement)
    if row is None:
        raise EstimatingValidationError("Budget was not found")
    return row


async def _approved_source_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    source_boq_id: UUID,
) -> BOQ:
    row = await db.scalar(
        select(BOQ).where(
            BOQ.id == source_boq_id,
            BOQ.organization_id == organization_id,
            BOQ.project_id == project_id,
        )
    )
    if row is None:
        raise EstimatingValidationError("Source BOQ was not found in this project")
    if row.status != BOQStatus.APPROVED:
        raise EstimatingValidationError("Only an approved BOQ can be used as an estimate source")
    return row


async def create_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectEstimate:
    data = dict(values)
    source_boq_id = data.get("source_boq_id")
    if isinstance(source_boq_id, UUID):
        boq = await _approved_source_boq(
            db,
            organization_id=organization_id,
            project_id=project_id,
            source_boq_id=source_boq_id,
        )
        requested_currency = str(data.get("currency_code") or boq.currency_code).upper()
        if requested_currency != boq.currency_code:
            raise EstimatingValidationError("Estimate currency must match its source BOQ currency")
        data["currency_code"] = boq.currency_code
    return await legacy.create_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values=data,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def copy_source_boq_items(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectEstimate:
    estimate = await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
        for_update=True,
    )
    if estimate.status != EstimateStatus.DRAFT:
        raise EstimatingValidationError("Only a draft estimate can import BOQ items")
    if estimate.revision != expected_revision:
        raise EstimatingConflictError("Estimate changed; refresh before importing BOQ items")
    if estimate.source_boq_id is None:
        raise EstimatingValidationError("Estimate does not have a source BOQ")
    boq = await _approved_source_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        source_boq_id=estimate.source_boq_id,
    )
    existing_count = int(
        await db.scalar(select(func.count(EstimateItem.id)).where(EstimateItem.estimate_id == estimate.id))
        or 0
    )
    if existing_count:
        raise EstimatingValidationError("BOQ items can only be copied into an empty estimate")
    items = list(
        (
            await db.scalars(
                select(BOQItem)
                .where(
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQItem.boq_id == boq.id,
                )
                .order_by(BOQItem.line_number)
            )
        ).all()
    )
    if not items:
        raise EstimatingValidationError("Source BOQ has no items")
    for item in items:
        if item.wbs_code_id is not None:
            wbs = await db.scalar(
                select(WBSCode).where(
                    WBSCode.id == item.wbs_code_id,
                    WBSCode.organization_id == organization_id,
                    WBSCode.project_id == project_id,
                )
            )
            if wbs is None or wbs.status != RecordStatus.ACTIVE:
                raise EstimatingValidationError(
                    f"BOQ item {item.item_code} references an inactive or missing WBS code"
                )
        db.add(
            EstimateItem(
                organization_id=organization_id,
                project_id=project_id,
                estimate_id=estimate.id,
                wbs_code_id=item.wbs_code_id,
                boq_item_id=item.id,
                line_number=item.line_number,
                item_code=item.item_code,
                description=item.description,
                unit_code=item.unit_code,
                quantity=item.quantity,
                rate=Decimal("0.00"),
                amount=Decimal("0.00"),
                notes="Copied from approved BOQ; internal rate requires rate analysis.",
            )
        )
    estimate.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.estimate.boq_items_copied",
        target_type="project_estimate",
        target_id=str(estimate.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"source_boq_id": str(boq.id), "item_count": len(items), "revision": estimate.revision},
    )
    await legacy._publish(
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
    estimate = await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
    )
    data = dict(values)
    wbs_id = data.get("wbs_code_id")
    if isinstance(wbs_id, UUID):
        wbs = await db.scalar(
            select(WBSCode).where(
                WBSCode.id == wbs_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if wbs is None or wbs.status != RecordStatus.ACTIVE:
            raise EstimatingValidationError("Estimate items can only use an active WBS code")
    boq_item_id = data.get("boq_item_id")
    if isinstance(boq_item_id, UUID):
        if estimate.source_boq_id is None:
            raise EstimatingValidationError("BOQ item references require an estimate source BOQ")
        boq_item = await db.scalar(
            select(BOQItem).where(
                BOQItem.id == boq_item_id,
                BOQItem.organization_id == organization_id,
                BOQItem.project_id == project_id,
                BOQItem.boq_id == estimate.source_boq_id,
            )
        )
        if boq_item is None:
            raise EstimatingValidationError("BOQ item does not belong to this estimate's source BOQ")
    return await legacy.add_estimate_item(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
        values=data,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def create_rate_analysis(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> RateAnalysis:
    return await legacy.create_rate_analysis(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values=values,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )


async def _current_analysis_payload(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    item: EstimateItem,
) -> dict[str, object]:
    analysis = await db.scalar(
        select(RateAnalysis).where(
            RateAnalysis.organization_id == organization_id,
            RateAnalysis.project_id == project_id,
            RateAnalysis.estimate_item_id == item.id,
            RateAnalysis.is_current.is_(True),
        )
    )
    if analysis is None:
        raise EstimatingValidationError(
            f"Estimate item {item.item_code} requires a current rate analysis before approval"
        )
    components = list(
        (
            await db.scalars(
                select(RateAnalysisComponent)
                .where(
                    RateAnalysisComponent.organization_id == organization_id,
                    RateAnalysisComponent.project_id == project_id,
                    RateAnalysisComponent.analysis_id == analysis.id,
                )
                .order_by(RateAnalysisComponent.created_at)
            )
        ).all()
    )
    if not components:
        raise EstimatingValidationError(
            f"Estimate item {item.item_code} rate analysis has no components"
        )
    base = money(sum((Decimal(component.amount) for component in components), start=Decimal("0")))
    breakdown = rate_breakdown(
        base,
        Decimal(analysis.wastage_percent),
        Decimal(analysis.overhead_percent),
        Decimal(analysis.profit_percent),
    )
    quantity = Decimal(item.quantity)
    category_base: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for component in components:
        category = component.kind.value
        category_base[category] += Decimal(component.amount)
    category_cost: dict[str, Decimal] = {}
    for category, amount in category_base.items():
        share = (amount / base) if base else Decimal("0")
        category_cost[category] = money(
            (amount + breakdown["wastage_amount"] * share) * quantity
        )
    overhead_extended = money(breakdown["overhead_amount"] * quantity)
    category_cost[BudgetCategory.OVERHEAD.value] = money(
        category_cost.get(BudgetCategory.OVERHEAD.value, Decimal("0")) + overhead_extended
    )
    expected_cost = money(breakdown["cost_rate"] * quantity)
    actual_cost = money(sum(category_cost.values(), start=Decimal("0")))
    rounding_delta = money(expected_cost - actual_cost)
    if rounding_delta:
        category_cost[BudgetCategory.OVERHEAD.value] = money(
            category_cost.get(BudgetCategory.OVERHEAD.value, Decimal("0")) + rounding_delta
        )
    return {
        "id": str(analysis.id),
        "version_number": analysis.version_number,
        "wastage_percent": str(analysis.wastage_percent),
        "overhead_percent": str(analysis.overhead_percent),
        "profit_percent": str(analysis.profit_percent),
        "base_rate": str(breakdown["base_rate"]),
        "wastage_amount": str(breakdown["wastage_amount"]),
        "overhead_amount": str(breakdown["overhead_amount"]),
        "cost_rate": str(breakdown["cost_rate"]),
        "profit_amount": str(breakdown["profit_amount"]),
        "selling_rate": str(breakdown["selling_rate"]),
        "extended_cost": str(expected_cost),
        "extended_profit": str(money(breakdown["profit_amount"] * quantity)),
        "extended_selling": str(money(breakdown["selling_rate"] * quantity)),
        "budget_categories": {key: str(value) for key, value in sorted(category_cost.items())},
        "components": [
            {
                "id": str(component.id),
                "kind": component.kind.value,
                "description": component.description,
                "unit_code": component.unit_code,
                "quantity": str(component.quantity),
                "unit_rate": str(component.unit_rate),
                "amount": str(component.amount),
                "source_entity_type": component.source_entity_type,
                "source_entity_id": str(component.source_entity_id) if component.source_entity_id else None,
            }
            for component in components
        ],
    }


async def _build_estimate_snapshot(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate: ProjectEstimate,
    version_number: int,
    approved_at: datetime,
) -> dict[str, object]:
    if estimate.source_boq_id is not None:
        source_boq = await _approved_source_boq(
            db,
            organization_id=organization_id,
            project_id=project_id,
            source_boq_id=estimate.source_boq_id,
        )
        if source_boq.currency_code != estimate.currency_code:
            raise EstimatingValidationError("Estimate currency no longer matches its source BOQ")
    items = list(
        (
            await db.scalars(
                select(EstimateItem)
                .where(
                    EstimateItem.organization_id == organization_id,
                    EstimateItem.project_id == project_id,
                    EstimateItem.estimate_id == estimate.id,
                )
                .order_by(EstimateItem.line_number)
            )
        ).all()
    )
    if not items:
        raise EstimatingValidationError("Estimate cannot be approved without items")
    snapshot_items: list[dict[str, object]] = []
    budget_breakdown: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    total_cost = Decimal("0")
    total_profit = Decimal("0")
    total_selling = Decimal("0")
    for item in items:
        if item.wbs_code_id is None:
            raise EstimatingValidationError(
                f"Estimate item {item.item_code} requires a WBS code before approval"
            )
        wbs = await db.scalar(
            select(WBSCode).where(
                WBSCode.id == item.wbs_code_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if wbs is None or wbs.status != RecordStatus.ACTIVE:
            raise EstimatingValidationError(
                f"Estimate item {item.item_code} requires an active WBS code before approval"
            )
        if item.boq_item_id is not None:
            if estimate.source_boq_id is None:
                raise EstimatingValidationError("BOQ-linked estimate item has no source BOQ")
            boq_item = await db.scalar(
                select(BOQItem).where(
                    BOQItem.id == item.boq_item_id,
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQItem.boq_id == estimate.source_boq_id,
                )
            )
            if boq_item is None:
                raise EstimatingValidationError(
                    f"Estimate item {item.item_code} no longer matches the source BOQ"
                )
        analysis = await _current_analysis_payload(
            db,
            organization_id=organization_id,
            project_id=project_id,
            item=item,
        )
        cost = Decimal(str(analysis["extended_cost"]))
        profit = Decimal(str(analysis["extended_profit"]))
        selling = Decimal(str(analysis["extended_selling"]))
        total_cost += cost
        total_profit += profit
        total_selling += selling
        for category, amount in dict(analysis["budget_categories"]).items():
            budget_breakdown[(str(wbs.id), category)] += Decimal(str(amount))
        snapshot_items.append(
            {
                "id": str(item.id),
                "line_number": item.line_number,
                "item_code": item.item_code,
                "description": item.description,
                "unit_code": item.unit_code,
                "quantity": str(item.quantity),
                "wbs_code_id": str(wbs.id),
                "wbs_code": wbs.code,
                "boq_item_id": str(item.boq_item_id) if item.boq_item_id else None,
                "revision": item.revision,
                "rate_analysis": analysis,
            }
        )
    return {
        "estimate": {
            "id": str(estimate.id),
            "code": estimate.code,
            "name": estimate.name,
            "description": estimate.description,
            "currency_code": estimate.currency_code,
            "source_boq_id": str(estimate.source_boq_id) if estimate.source_boq_id else None,
            "revision": estimate.revision,
            "version_number": version_number,
            "approved_at": approved_at.isoformat(),
            "total_cost": str(money(total_cost)),
            "total_profit": str(money(total_profit)),
            "total_selling": str(money(total_selling)),
        },
        "items": snapshot_items,
        "budget_breakdown": [
            {
                "wbs_code_id": wbs_id,
                "category": category,
                "amount": str(money(amount)),
            }
            for (wbs_id, category), amount in sorted(budget_breakdown.items())
        ],
    }


async def submit_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectEstimate:
    estimate = await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
    )
    count = int(
        await db.scalar(select(func.count(EstimateItem.id)).where(EstimateItem.estimate_id == estimate.id))
        or 0
    )
    if not count:
        raise EstimatingValidationError("Estimate cannot be submitted without items")
    return await legacy.transition_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
        expected_revision=expected_revision,
        target=EstimateStatus.SUBMITTED,
        actor_user_id=actor_user_id,
        actor_membership_id=actor_membership_id,
        session_id=session_id,
        reason=reason,
    )


async def approve_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ProjectEstimate:
    estimate = await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
        for_update=True,
    )
    if estimate.status != EstimateStatus.SUBMITTED:
        raise EstimatingValidationError("Only a submitted estimate can be approved")
    if estimate.revision != expected_revision:
        raise EstimatingConflictError("Estimate changed; refresh before approval")
    await legacy._require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=actor_membership_id,
    )
    version = int(
        await db.scalar(
            select(func.coalesce(func.max(EstimateApprovalSnapshot.version_number), 0)).where(
                EstimateApprovalSnapshot.estimate_id == estimate.id
            )
        )
        or 0
    ) + 1
    approved_at = datetime.now(UTC)
    snapshot = await _build_estimate_snapshot(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate=estimate,
        version_number=version,
        approved_at=approved_at,
    )
    estimate.status = EstimateStatus.APPROVED
    estimate.approved_by_membership_id = actor_membership_id
    estimate.approved_at = approved_at
    estimate.revision += 1
    snapshot["estimate"]["revision"] = estimate.revision
    db.add(
        EstimateApprovalSnapshot(
            organization_id=organization_id,
            project_id=project_id,
            estimate_id=estimate.id,
            version_number=version,
            estimate_revision=estimate.revision,
            approved_by_membership_id=actor_membership_id,
            approved_at=approved_at,
            reason=reason,
            snapshot_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
        )
    )
    revision_link = await db.scalar(
        select(EstimateRevisionLink).where(
            EstimateRevisionLink.organization_id == organization_id,
            EstimateRevisionLink.project_id == project_id,
            EstimateRevisionLink.revised_estimate_id == estimate.id,
        )
    )
    if revision_link is not None:
        prior = await db.scalar(
            select(ProjectEstimate).where(
                ProjectEstimate.id == revision_link.prior_estimate_id,
                ProjectEstimate.organization_id == organization_id,
                ProjectEstimate.project_id == project_id,
            )
        )
        if prior is not None and prior.status == EstimateStatus.APPROVED:
            prior.status = EstimateStatus.SUPERSEDED
            prior.revision += 1
            await legacy._publish(
                db,
                organization_id=organization_id,
                project_id=project_id,
                event_type="estimating.estimate.superseded",
                entity_type="project_estimate",
                entity_id=prior.id,
                entity_version=prior.revision,
                permission="estimating.estimate.view",
                actor_user_id=actor_user_id,
                session_id=session_id,
            )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.estimate.approved",
        target_type="project_estimate",
        target_id=str(estimate.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "status": estimate.status.value,
            "revision": estimate.revision,
            "snapshot_version": version,
            "total_cost": snapshot["estimate"]["total_cost"],
            "total_selling": snapshot["estimate"]["total_selling"],
        },
    )
    await legacy._publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.estimate.approved",
        entity_type="project_estimate",
        entity_id=estimate.id,
        entity_version=estimate.revision,
        permission="estimating.estimate.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return estimate


async def revise_estimate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
    new_code: str,
    new_name: str,
    reason: str,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
) -> ProjectEstimate:
    prior = await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
        for_update=True,
    )
    if prior.status != EstimateStatus.APPROVED:
        raise EstimatingValidationError("Only an approved estimate can be revised")
    if not reason.strip():
        raise EstimatingValidationError("A reason is required to revise an approved estimate")
    code = new_code.strip().upper()
    name = new_name.strip()
    if not code or not name:
        raise EstimatingValidationError("New estimate code and name are required")
    duplicate = await db.scalar(
        select(ProjectEstimate.id).where(
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.code == code,
        )
    )
    if duplicate is not None:
        raise EstimatingConflictError("Estimate code already exists in this project")
    revised = ProjectEstimate(
        organization_id=organization_id,
        project_id=project_id,
        source_boq_id=prior.source_boq_id,
        code=code,
        name=name,
        description=prior.description,
        currency_code=prior.currency_code,
    )
    db.add(revised)
    await db.flush()
    prior_items = list(
        (
            await db.scalars(
                select(EstimateItem)
                .where(EstimateItem.estimate_id == prior.id)
                .order_by(EstimateItem.line_number)
            )
        ).all()
    )
    for prior_item in prior_items:
        cloned_item = EstimateItem(
            organization_id=organization_id,
            project_id=project_id,
            estimate_id=revised.id,
            wbs_code_id=prior_item.wbs_code_id,
            boq_item_id=prior_item.boq_item_id,
            line_number=prior_item.line_number,
            item_code=prior_item.item_code,
            description=prior_item.description,
            unit_code=prior_item.unit_code,
            quantity=prior_item.quantity,
            rate=prior_item.rate,
            amount=prior_item.amount,
            notes=prior_item.notes,
        )
        db.add(cloned_item)
        await db.flush()
        analysis = await db.scalar(
            select(RateAnalysis).where(
                RateAnalysis.estimate_item_id == prior_item.id,
                RateAnalysis.is_current.is_(True),
            )
        )
        if analysis is not None:
            cloned_analysis = RateAnalysis(
                organization_id=organization_id,
                project_id=project_id,
                estimate_item_id=cloned_item.id,
                version_number=1,
                wastage_percent=analysis.wastage_percent,
                overhead_percent=analysis.overhead_percent,
                profit_percent=analysis.profit_percent,
                calculated_rate=analysis.calculated_rate,
                is_current=True,
                notes=analysis.notes,
            )
            db.add(cloned_analysis)
            await db.flush()
            components = list(
                (
                    await db.scalars(
                        select(RateAnalysisComponent).where(
                            RateAnalysisComponent.analysis_id == analysis.id
                        )
                    )
                ).all()
            )
            for component in components:
                db.add(
                    RateAnalysisComponent(
                        organization_id=organization_id,
                        project_id=project_id,
                        analysis_id=cloned_analysis.id,
                        kind=component.kind,
                        description=component.description,
                        unit_code=component.unit_code,
                        quantity=component.quantity,
                        unit_rate=component.unit_rate,
                        amount=component.amount,
                        source_entity_type=component.source_entity_type,
                        source_entity_id=component.source_entity_id,
                    )
                )
    db.add(
        EstimateRevisionLink(
            organization_id=organization_id,
            project_id=project_id,
            prior_estimate_id=prior.id,
            revised_estimate_id=revised.id,
            created_by_membership_id=actor_membership_id,
            reason=reason.strip(),
        )
    )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="estimating.estimate.revision_created",
        target_type="project_estimate",
        target_id=str(revised.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"prior_estimate_id": str(prior.id), "new_code": revised.code},
    )
    await legacy._publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.estimate.created",
        entity_type="project_estimate",
        entity_id=revised.id,
        entity_version=revised.revision,
        permission="estimating.estimate.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return revised


async def list_estimate_snapshots(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    estimate_id: UUID,
) -> list[EstimateApprovalSnapshot]:
    await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
    )
    rows = await db.scalars(
        select(EstimateApprovalSnapshot)
        .where(
            EstimateApprovalSnapshot.organization_id == organization_id,
            EstimateApprovalSnapshot.project_id == project_id,
            EstimateApprovalSnapshot.estimate_id == estimate_id,
        )
        .order_by(EstimateApprovalSnapshot.version_number.desc())
    )
    return list(rows.all())


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
    estimate = await _load_estimate(
        db,
        organization_id=organization_id,
        project_id=project_id,
        estimate_id=estimate_id,
    )
    if estimate.status != EstimateStatus.APPROVED:
        raise EstimatingValidationError("Budget can only be generated from an approved estimate")
    existing = await db.scalar(
        select(ProjectBudget.id).where(
            ProjectBudget.organization_id == organization_id,
            ProjectBudget.project_id == project_id,
            ProjectBudget.estimate_id == estimate_id,
            ProjectBudget.status.in_([BudgetStatus.DRAFT, BudgetStatus.APPROVED]),
        )
    )
    if existing is not None:
        raise EstimatingConflictError(
            "This approved estimate already has a current draft or approved budget"
        )
    snapshot = await db.scalar(
        select(EstimateApprovalSnapshot)
        .where(
            EstimateApprovalSnapshot.organization_id == organization_id,
            EstimateApprovalSnapshot.project_id == project_id,
            EstimateApprovalSnapshot.estimate_id == estimate_id,
        )
        .order_by(EstimateApprovalSnapshot.version_number.desc())
    )
    if snapshot is None:
        raise EstimatingValidationError("Approved estimate has no immutable approval snapshot")
    payload = json.loads(snapshot.snapshot_json)
    estimate_snapshot = payload.get("estimate") or {}
    budget = await legacy.create_budget(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values={
            "estimate_id": estimate_id,
            "code": code,
            "name": name,
            "currency_code": estimate_snapshot.get("currency_code") or estimate.currency_code,
            "notes": f"Generated from approved estimate {estimate.code} snapshot v{snapshot.version_number}",
        },
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    breakdown = payload.get("budget_breakdown") or []
    if not breakdown:
        raise EstimatingValidationError("Approved estimate snapshot has no budget cost breakdown")
    total = Decimal("0")
    for row in breakdown:
        amount = money(Decimal(str(row["amount"])))
        total += amount
        db.add(
            BudgetLine(
                organization_id=organization_id,
                project_id=project_id,
                budget_id=budget.id,
                wbs_code_id=UUID(str(row["wbs_code_id"])),
                category=BudgetCategory(str(row["category"])),
                amount=amount,
                notes=f"Estimate snapshot {snapshot.version_number}",
            )
        )
    expected_total = money(Decimal(str(estimate_snapshot.get("total_cost") or 0)))
    if money(total) != expected_total:
        raise EstimatingValidationError("Budget cost breakdown does not reconcile to approved estimate cost")
    budget.revision += 1
    await db.flush()
    await legacy._publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="estimating.budget.generated",
        entity_type="project_budget",
        entity_id=budget.id,
        entity_version=budget.revision,
        permission="estimating.budget.view",
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
    budget = await _load_budget(
        db,
        organization_id=organization_id,
        project_id=project_id,
        budget_id=budget_id,
        for_update=True,
    )
    if budget.status != BudgetStatus.DRAFT:
        raise EstimatingValidationError("Only a draft budget can be approved")
    if budget.revision != expected_revision:
        raise EstimatingConflictError("Budget changed; refresh before approval")
    await legacy._require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=actor_membership_id,
    )
    lines = list(
        (
            await db.scalars(
                select(BudgetLine)
                .where(
                    BudgetLine.organization_id == organization_id,
                    BudgetLine.project_id == project_id,
                    BudgetLine.budget_id == budget.id,
                )
                .order_by(BudgetLine.wbs_code_id, BudgetLine.category)
            )
        ).all()
    )
    if not lines:
        raise EstimatingValidationError("Budget cannot be approved without lines")
    estimate_snapshot = None
    if budget.estimate_id is not None:
        estimate_snapshot = await db.scalar(
            select(EstimateApprovalSnapshot)
            .where(
                EstimateApprovalSnapshot.organization_id == organization_id,
                EstimateApprovalSnapshot.project_id == project_id,
                EstimateApprovalSnapshot.estimate_id == budget.estimate_id,
            )
            .order_by(EstimateApprovalSnapshot.version_number.desc())
        )
        if estimate_snapshot is None:
            raise EstimatingValidationError("Budget source estimate has no approval snapshot")
        estimate_payload = json.loads(estimate_snapshot.snapshot_json)
        if (estimate_payload.get("estimate") or {}).get("currency_code") != budget.currency_code:
            raise EstimatingValidationError("Budget currency does not match its approved estimate")
    approved_at = datetime.now(UTC)
    version = int(
        await db.scalar(
            select(func.coalesce(func.max(BudgetApprovalSnapshot.version_number), 0)).where(
                BudgetApprovalSnapshot.budget_id == budget.id
            )
        )
        or 0
    ) + 1
    total_amount = money(sum((Decimal(line.amount) for line in lines), start=Decimal("0")))
    snapshot_payload = {
        "budget": {
            "id": str(budget.id),
            "code": budget.code,
            "name": budget.name,
            "currency_code": budget.currency_code,
            "estimate_id": str(budget.estimate_id) if budget.estimate_id else None,
            "revision": budget.revision + 1,
            "version_number": version,
            "approved_at": approved_at.isoformat(),
            "total_amount": str(total_amount),
        },
        "lines": [
            {
                "id": str(line.id),
                "wbs_code_id": str(line.wbs_code_id),
                "category": line.category.value,
                "amount": str(line.amount),
                "notes": line.notes,
                "revision": line.revision,
            }
            for line in lines
        ],
    }
    prior_approved = list(
        (
            await db.scalars(
                select(ProjectBudget).where(
                    ProjectBudget.organization_id == organization_id,
                    ProjectBudget.project_id == project_id,
                    ProjectBudget.status == BudgetStatus.APPROVED,
                    ProjectBudget.id != budget.id,
                )
            )
        ).all()
    )
    for prior in prior_approved:
        prior.status = BudgetStatus.SUPERSEDED
        prior.revision += 1
        await legacy._publish(
            db,
            organization_id=organization_id,
            project_id=project_id,
            event_type="estimating.budget.superseded",
            entity_type="project_budget",
            entity_id=prior.id,
            entity_version=prior.revision,
            permission="estimating.budget.view",
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    budget.status = BudgetStatus.APPROVED
    budget.approved_by_membership_id = actor_membership_id
    budget.approved_at = approved_at
    budget.revision += 1
    db.add(
        BudgetApprovalSnapshot(
            organization_id=organization_id,
            project_id=project_id,
            budget_id=budget.id,
            estimate_snapshot_id=estimate_snapshot.id if estimate_snapshot is not None else None,
            version_number=version,
            budget_revision=budget.revision,
            approved_by_membership_id=actor_membership_id,
            approved_at=approved_at,
            reason=reason,
            snapshot_json=json.dumps(snapshot_payload, separators=(",", ":"), sort_keys=True),
        )
    )
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
        changes={"status": budget.status.value, "revision": budget.revision, "total_amount": str(total_amount)},
    )
    await legacy._publish(
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


async def list_budget_snapshots(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    budget_id: UUID,
) -> list[BudgetApprovalSnapshot]:
    await _load_budget(
        db,
        organization_id=organization_id,
        project_id=project_id,
        budget_id=budget_id,
    )
    rows = await db.scalars(
        select(BudgetApprovalSnapshot)
        .where(
            BudgetApprovalSnapshot.organization_id == organization_id,
            BudgetApprovalSnapshot.project_id == project_id,
            BudgetApprovalSnapshot.budget_id == budget_id,
        )
        .order_by(BudgetApprovalSnapshot.version_number.desc())
    )
    return list(rows.all())
