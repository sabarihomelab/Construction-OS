from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
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
from app.modules.subcontracts.models import (
    Subcontract,
    SubcontractClaim,
    SubcontractClaimLine,
    SubcontractClaimStatus,
    SubcontractLine,
)


async def post_subcontract_claim_cost(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    subcontract_cost_head_id: UUID,
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
            ProjectCostEntry.source_type == ProjectCostSourceType.SUBCONTRACT_CLAIM,
            ProjectCostEntry.source_id == claim_id,
        )
    )
    if existing is not None:
        if existing.status == ProjectCostStatus.POSTED:
            return existing
        raise FinancialConflictError(
            "This subcontract claim already has a non-posted project cost record"
        )

    claim = await db.scalar(
        select(SubcontractClaim).where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.organization_id == organization_id,
            SubcontractClaim.project_id == project_id,
        )
    )
    if claim is None:
        raise FinancialValidationError("Subcontract claim was not found in this project")
    if claim.status not in {
        SubcontractClaimStatus.CERTIFIED,
        SubcontractClaimStatus.PAID,
    }:
        raise FinancialValidationError(
            "Only a certified subcontract claim can become project cost"
        )
    if claim.certified_at is None:
        raise FinancialValidationError(
            "Certified subcontract claim is missing its authoritative certification timestamp"
        )

    subcontract = await db.scalar(
        select(Subcontract).where(
            Subcontract.id == claim.subcontract_id,
            Subcontract.organization_id == organization_id,
            Subcontract.project_id == project_id,
        )
    )
    if subcontract is None:
        raise FinancialValidationError("Subcontract was not found for this claim")

    project_currency = (project.currency_code or "INR").upper()
    if subcontract.currency_code.upper() != project_currency:
        raise FinancialValidationError(
            "Subcontract currency must match project currency before cost posting"
        )

    cost_head = await db.scalar(
        select(CostHead).where(
            CostHead.id == subcontract_cost_head_id,
            CostHead.organization_id == organization_id,
        )
    )
    if (
        cost_head is None
        or cost_head.status != RecordStatus.ACTIVE
        or not cost_head.allows_posting
        or cost_head.category != CostHeadCategory.SUBCONTRACT
    ):
        raise FinancialValidationError(
            "Subcontract costing requires an active posting Subcontract Cost Head"
        )

    claim_lines = list(
        (
            await db.scalars(
                select(SubcontractClaimLine)
                .where(
                    SubcontractClaimLine.organization_id == organization_id,
                    SubcontractClaimLine.project_id == project_id,
                    SubcontractClaimLine.claim_id == claim.id,
                )
                .order_by(SubcontractClaimLine.id)
            )
        ).all()
    )
    cost_lines = [line for line in claim_lines if line.certified_amount > Decimal(0)]
    if not cost_lines:
        raise FinancialValidationError(
            "Certified subcontract claim has no positive certified work value"
        )

    subcontract_line_ids = {line.subcontract_line_id for line in cost_lines}
    contract_lines = {
        line.id: line
        for line in (
            await db.scalars(
                select(SubcontractLine).where(
                    SubcontractLine.id.in_(subcontract_line_ids),
                    SubcontractLine.organization_id == organization_id,
                    SubcontractLine.project_id == project_id,
                    SubcontractLine.subcontract_id == subcontract.id,
                )
            )
        ).all()
    }
    if len(contract_lines) != len(subcontract_line_ids):
        raise FinancialValidationError(
            "One or more subcontract claim lines are missing their authoritative work-order line"
        )

    gross_certified_work = sum(
        (line.certified_amount for line in cost_lines),
        start=Decimal(0),
    ).quantize(Decimal("0.01"))
    if gross_certified_work != claim.gross_amount:
        raise FinancialConflictError(
            "Subcontract claim gross amount does not reconcile to its certified lines"
        )

    entry_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="project_cost",
        prefix="COST",
    )
    now = datetime.now(UTC)
    cost_entry = ProjectCostEntry(
        organization_id=organization_id,
        project_id=project_id,
        entry_number=entry_number,
        entry_date=claim.period_to,
        source_type=ProjectCostSourceType.SUBCONTRACT_CLAIM,
        source_id=claim.id,
        source_reference=claim.number,
        description=f"Subcontract certified work · {subcontract.number}",
        total_amount=gross_certified_work,
        currency_code=project_currency,
        status=ProjectCostStatus.POSTED,
        configuration_context={
            "subcontract_id": str(subcontract.id),
            "subcontract_number": subcontract.number,
            "subcontract_claim_id": str(claim.id),
            "claim_number": claim.number,
            "claim_revision": claim.revision,
            "certified_at": claim.certified_at.isoformat(),
            "gross_certified_work": str(gross_certified_work),
            "retention_amount": str(claim.retention_amount),
            "other_deductions": str(claim.other_deductions),
            "tax_withheld_amount": str(claim.tax_withheld_amount),
            "net_certified_payable": str(claim.certified_amount),
            "cost_basis": "gross_certified_subcontract_work",
        },
        revision=1,
        posted_by_membership_id=membership_id,
        posted_at=now,
    )
    db.add(cost_entry)
    await db.flush()

    for line_number, claim_line in enumerate(cost_lines, start=1):
        contract_line = contract_lines[claim_line.subcontract_line_id]
        db.add(
            ProjectCostAllocation(
                organization_id=organization_id,
                project_id=project_id,
                cost_entry_id=cost_entry.id,
                line_number=line_number,
                cost_head_id=cost_head.id,
                wbs_code_id=contract_line.wbs_code_id,
                boq_item_id=contract_line.boq_item_id,
                party_id=subcontract.contractor_party_id,
                description=contract_line.description,
                quantity=claim_line.certified_quantity,
                unit_code=contract_line.unit_code,
                amount=claim_line.certified_amount,
            )
        )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.project_cost.subcontract_claim.posted",
        target_type="project_cost_entry",
        target_id=str(cost_entry.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "project_id": str(project_id),
            "subcontract_id": str(subcontract.id),
            "subcontract_claim_id": str(claim.id),
            "amount": gross_certified_work,
            "currency_code": project_currency,
            "cost_basis": "gross_certified_subcontract_work",
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
            "source_type": ProjectCostSourceType.SUBCONTRACT_CLAIM.value,
            "source_id": str(claim.id),
            "subcontract_id": str(subcontract.id),
            "amount": str(gross_certified_work),
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
