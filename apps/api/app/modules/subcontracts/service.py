from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import (
    BOQItem,
    MeasurementEntry,
    MeasurementStatus,
    Party,
    PartyStatus,
    PartyType,
    WBSCode,
)
from app.modules.events.service import enqueue_event
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.search.service import schedule_search_index
from app.modules.subcontracts.models import (
    Subcontract,
    SubcontractClaim,
    SubcontractClaimLine,
    SubcontractClaimStatus,
    SubcontractLine,
    SubcontractStatus,
)
from app.modules.subcontracts.numbering import allocate_subcontract_number


class SubcontractValidationError(ValueError):
    pass


class SubcontractConflictError(ValueError):
    pass


MONEY = Decimal("0.01")
HUNDRED = Decimal(100)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    exists = await db.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if exists is None:
        raise SubcontractValidationError("Project was not found")


async def _require_project_member(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    member = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if member is None:
        raise SubcontractValidationError("User must be an active member of this project")


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


async def create_subcontract(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> Subcontract:
    await _require_project(db, organization_id, project_id)
    contractor_id = values.get("contractor_party_id")
    if not isinstance(contractor_id, UUID):
        raise SubcontractValidationError("Contractor is required")
    contractor = await db.scalar(
        select(Party).where(Party.id == contractor_id, Party.organization_id == organization_id)
    )
    allowed_types = {PartyType.SUBCONTRACTOR, PartyType.LABOUR_CONTRACTOR, PartyType.OTHER}
    if contractor is None or contractor.status != PartyStatus.ACTIVE or contractor.party_type not in allowed_types:
        raise SubcontractValidationError("Active subcontractor or labour contractor was not found")
    title = str(values.get("title") or "").strip()
    if not title:
        raise SubcontractValidationError("Work order title is required")
    start_date = values.get("start_date")
    end_date = values.get("end_date")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise SubcontractValidationError("End date cannot be before start date")
    number = await allocate_subcontract_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="contract",
    )
    row = Subcontract(
        organization_id=organization_id,
        project_id=project_id,
        number=f"WO-{number:05d}",
        contractor_party_id=contractor_id,
        title=title,
        description=values.get("description"),
        currency_code=str(values.get("currency_code") or "INR").upper(),
        start_date=start_date,
        end_date=end_date,
        retention_percent=Decimal(values.get("retention_percent") or 0),
        notes=values.get("notes"),
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.contract.created",
        target_type="subcontract",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"number": row.number, "contractor_party_id": str(contractor_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.contract.created",
        entity_type="subcontract",
        entity_id=row.id,
        entity_version=row.revision,
        permission="subcontracts.contract.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def add_subcontract_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subcontract_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SubcontractLine:
    contract = await db.scalar(
        select(Subcontract)
        .where(
            Subcontract.id == subcontract_id,
            Subcontract.project_id == project_id,
            Subcontract.organization_id == organization_id,
        )
        .with_for_update()
    )
    if contract is None:
        raise SubcontractValidationError("Work order was not found")
    if contract.status != SubcontractStatus.DRAFT:
        raise SubcontractValidationError("Only draft work orders can be edited")
    data = dict(values)
    wbs_id = data.get("wbs_code_id")
    if isinstance(wbs_id, UUID):
        exists = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_id,
                WBSCode.project_id == project_id,
                WBSCode.organization_id == organization_id,
            )
        )
        if exists is None:
            raise SubcontractValidationError("WBS code was not found in this project")
    boq_id = data.get("boq_item_id")
    if isinstance(boq_id, UUID):
        exists = await db.scalar(
            select(BOQItem.id).where(
                BOQItem.id == boq_id,
                BOQItem.project_id == project_id,
                BOQItem.organization_id == organization_id,
            )
        )
        if exists is None:
            raise SubcontractValidationError("BOQ item was not found in this project")
    quantity = Decimal(data.get("quantity") or 0)
    rate = money(Decimal(data.get("rate") or 0))
    data["quantity"] = quantity
    data["rate"] = rate
    data["amount"] = money(quantity * rate)
    line = SubcontractLine(
        organization_id=organization_id,
        project_id=project_id,
        subcontract_id=subcontract_id,
        **data,
    )
    db.add(line)
    await db.flush()
    total = await db.scalar(
        select(func.coalesce(func.sum(SubcontractLine.amount), 0)).where(
            SubcontractLine.subcontract_id == subcontract_id
        )
    )
    contract.original_amount = money(Decimal(total or 0))
    contract.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.line.created",
        target_type="subcontract_line",
        target_id=str(line.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"subcontract_id": str(subcontract_id), "amount": str(line.amount)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.contract.updated",
        entity_type="subcontract",
        entity_id=contract.id,
        entity_version=contract.revision,
        permission="subcontracts.contract.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return line


async def transition_subcontract(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    subcontract_id: UUID,
    expected_revision: int,
    target: SubcontractStatus,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Subcontract:
    row = await db.scalar(
        select(Subcontract)
        .where(
            Subcontract.id == subcontract_id,
            Subcontract.project_id == project_id,
            Subcontract.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise SubcontractValidationError("Work order was not found")
    if row.revision != expected_revision:
        raise SubcontractConflictError("Work order changed; refresh before continuing")
    allowed = {
        SubcontractStatus.DRAFT: {SubcontractStatus.SUBMITTED, SubcontractStatus.CANCELLED},
        SubcontractStatus.SUBMITTED: {SubcontractStatus.APPROVED, SubcontractStatus.DRAFT},
        SubcontractStatus.APPROVED: {SubcontractStatus.ISSUED, SubcontractStatus.CANCELLED},
        SubcontractStatus.ISSUED: {SubcontractStatus.ACTIVE},
        SubcontractStatus.ACTIVE: {SubcontractStatus.COMPLETED},
    }
    if target not in allowed.get(row.status, set()):
        raise SubcontractValidationError(
            f"Work order cannot move from {row.status.value} to {target.value}"
        )
    if target == SubcontractStatus.SUBMITTED:
        count = await db.scalar(
            select(func.count(SubcontractLine.id)).where(SubcontractLine.subcontract_id == row.id)
        )
        if not count:
            raise SubcontractValidationError("Work order must contain at least one scope line")
    if target == SubcontractStatus.APPROVED:
        await _require_project_member(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=actor_membership_id,
        )
        row.approved_by_membership_id = actor_membership_id
        row.approved_at = datetime.now(UTC)
    if target == SubcontractStatus.ISSUED:
        row.issued_at = datetime.now(UTC)
    row.status = target
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"subcontracts.contract.{target.value}",
        target_type="subcontract",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL if target in {SubcontractStatus.APPROVED, SubcontractStatus.ISSUED} else AuditRisk.HIGH,
        reason=reason,
        changes={"status": target.value, "revision": row.revision, "amount": str(row.original_amount)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type=f"subcontracts.contract.{target.value}",
        entity_type="subcontract",
        entity_id=row.id,
        entity_version=row.revision,
        permission="subcontracts.contract.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def create_claim(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SubcontractClaim:
    subcontract_id = values.get("subcontract_id")
    if not isinstance(subcontract_id, UUID):
        raise SubcontractValidationError("Work order is required")
    contract = await db.scalar(
        select(Subcontract).where(
            Subcontract.id == subcontract_id,
            Subcontract.project_id == project_id,
            Subcontract.organization_id == organization_id,
        )
    )
    if contract is None or contract.status not in {SubcontractStatus.ISSUED, SubcontractStatus.ACTIVE}:
        raise SubcontractValidationError("Progress claims require an issued or active work order")
    period_from = values["period_from"]
    period_to = values["period_to"]
    if period_to < period_from:
        raise SubcontractValidationError("Claim period end cannot be before its start")
    number = await allocate_subcontract_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="claim",
    )
    row = SubcontractClaim(
        organization_id=organization_id,
        project_id=project_id,
        subcontract_id=subcontract_id,
        number=f"SC-{number:05d}",
        period_from=period_from,
        period_to=period_to,
        notes=values.get("notes"),
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.claim.created",
        target_type="subcontract_claim",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"number": row.number, "subcontract_id": str(subcontract_id)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.claim.created",
        entity_type="subcontract_claim",
        entity_id=row.id,
        entity_version=row.revision,
        permission="subcontracts.claim.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def add_claim_line(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SubcontractClaimLine:
    claim = await db.scalar(
        select(SubcontractClaim)
        .where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.organization_id == organization_id,
        )
        .with_for_update()
    )
    if claim is None:
        raise SubcontractValidationError("Progress claim was not found")
    if claim.status != SubcontractClaimStatus.DRAFT:
        raise SubcontractValidationError("Only draft claims can be edited")
    line_id = values.get("subcontract_line_id")
    if not isinstance(line_id, UUID):
        raise SubcontractValidationError("Work-order line is required")
    contract_line = await db.scalar(
        select(SubcontractLine).where(
            SubcontractLine.id == line_id,
            SubcontractLine.subcontract_id == claim.subcontract_id,
            SubcontractLine.project_id == project_id,
            SubcontractLine.organization_id == organization_id,
        )
    )
    if contract_line is None:
        raise SubcontractValidationError("Work-order line was not found for this claim")
    claimed = Decimal(values.get("claimed_quantity") or 0)
    previous = await db.scalar(
        select(func.coalesce(func.sum(SubcontractClaimLine.certified_quantity), 0))
        .join(SubcontractClaim, SubcontractClaim.id == SubcontractClaimLine.claim_id)
        .where(
            SubcontractClaimLine.subcontract_line_id == line_id,
            SubcontractClaim.status.in_({SubcontractClaimStatus.CERTIFIED, SubcontractClaimStatus.PAID}),
        )
    )
    if Decimal(previous or 0) + claimed > contract_line.quantity:
        raise SubcontractValidationError("Claim quantity exceeds remaining work-order quantity")
    measurement_id = values.get("measurement_entry_id")
    if isinstance(measurement_id, UUID):
        measurement = await db.scalar(
            select(MeasurementEntry).where(
                MeasurementEntry.id == measurement_id,
                MeasurementEntry.project_id == project_id,
                MeasurementEntry.organization_id == organization_id,
            )
        )
        if measurement is None or measurement.status != MeasurementStatus.CERTIFIED:
            raise SubcontractValidationError("Linked measurement must be certified")
        if contract_line.boq_item_id is not None and measurement.boq_item_id != contract_line.boq_item_id:
            raise SubcontractValidationError("Measurement BOQ item does not match the work-order line")
        if claimed > measurement.quantity:
            raise SubcontractValidationError("Claim quantity cannot exceed the linked certified measurement")
    gross = money(claimed * contract_line.rate)
    row = SubcontractClaimLine(
        organization_id=organization_id,
        project_id=project_id,
        claim_id=claim.id,
        subcontract_line_id=line_id,
        measurement_entry_id=measurement_id if isinstance(measurement_id, UUID) else None,
        claimed_quantity=claimed,
        rate=contract_line.rate,
        gross_amount=gross,
        remarks=values.get("remarks"),
    )
    db.add(row)
    await db.flush()
    total = await db.scalar(
        select(func.coalesce(func.sum(SubcontractClaimLine.gross_amount), 0)).where(
            SubcontractClaimLine.claim_id == claim.id
        )
    )
    claim.gross_amount = money(Decimal(total or 0))
    claim.revision += 1
    await db.flush()
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.claim.updated",
        entity_type="subcontract_claim",
        entity_id=claim.id,
        entity_version=claim.revision,
        permission="subcontracts.claim.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def submit_claim(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    claim = await db.scalar(
        select(SubcontractClaim)
        .where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.organization_id == organization_id,
        )
        .with_for_update()
    )
    if claim is None:
        raise SubcontractValidationError("Progress claim was not found")
    if claim.revision != expected_revision:
        raise SubcontractConflictError("Progress claim changed; refresh before submitting")
    if claim.status not in {SubcontractClaimStatus.DRAFT, SubcontractClaimStatus.REJECTED}:
        raise SubcontractValidationError("Only draft or rejected claims can be submitted")
    count = await db.scalar(
        select(func.count(SubcontractClaimLine.id)).where(SubcontractClaimLine.claim_id == claim.id)
    )
    if not count:
        raise SubcontractValidationError("Progress claim must contain at least one line")
    await _require_project_member(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=actor_membership_id,
    )
    claim.status = SubcontractClaimStatus.SUBMITTED
    claim.submitted_by_membership_id = actor_membership_id
    claim.submitted_at = datetime.now(UTC)
    claim.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.claim.submitted",
        target_type="subcontract_claim",
        target_id=str(claim.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": claim.status.value, "gross_amount": str(claim.gross_amount)},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.claim.submitted",
        entity_type="subcontract_claim",
        entity_id=claim.id,
        entity_version=claim.revision,
        permission="subcontracts.claim.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return claim


async def certify_claim(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    other_deductions: Decimal,
    tax_withheld_amount: Decimal,
    actor_user_id: UUID,
    actor_membership_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    claim = await db.scalar(
        select(SubcontractClaim)
        .where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.organization_id == organization_id,
        )
        .with_for_update()
    )
    if claim is None:
        raise SubcontractValidationError("Progress claim was not found")
    if claim.revision != expected_revision:
        raise SubcontractConflictError("Progress claim changed; refresh before certification")
    if claim.status != SubcontractClaimStatus.SUBMITTED:
        raise SubcontractValidationError("Only submitted claims can be certified")
    await _require_project_member(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=actor_membership_id,
    )
    contract = await db.scalar(
        select(Subcontract).where(Subcontract.id == claim.subcontract_id)
    )
    if contract is None:
        raise SubcontractValidationError("Work order was not found")
    lines = list(
        (
            await db.scalars(
                select(SubcontractClaimLine).where(SubcontractClaimLine.claim_id == claim.id)
            )
        ).all()
    )
    gross = money(sum((line.gross_amount for line in lines), start=Decimal(0)))
    retention = money(gross * contract.retention_percent / HUNDRED)
    deductions = money(other_deductions)
    withheld = money(tax_withheld_amount)
    net = money(gross - retention - deductions - withheld)
    if net < 0:
        raise SubcontractValidationError("Deductions and withholding cannot exceed the gross claim")
    for line in lines:
        line.certified_quantity = line.claimed_quantity
        line.certified_amount = line.gross_amount
    claim.gross_amount = gross
    claim.retention_amount = retention
    claim.other_deductions = deductions
    claim.tax_withheld_amount = withheld
    claim.certified_amount = net
    claim.certified_by_membership_id = actor_membership_id
    claim.certified_at = datetime.now(UTC)
    claim.status = SubcontractClaimStatus.CERTIFIED
    claim.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.claim.certified",
        target_type="subcontract_claim",
        target_id=str(claim.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "gross_amount": str(gross),
            "retention_amount": str(retention),
            "other_deductions": str(deductions),
            "tax_withheld_amount": str(withheld),
            "certified_amount": str(net),
        },
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.claim.certified",
        entity_type="subcontract_claim",
        entity_id=claim.id,
        entity_version=claim.revision,
        permission="subcontracts.claim.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return claim


async def record_claim_payment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    claim_id: UUID,
    expected_revision: int,
    payment_amount: Decimal,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SubcontractClaim:
    claim = await db.scalar(
        select(SubcontractClaim)
        .where(
            SubcontractClaim.id == claim_id,
            SubcontractClaim.project_id == project_id,
            SubcontractClaim.organization_id == organization_id,
        )
        .with_for_update()
    )
    if claim is None:
        raise SubcontractValidationError("Progress claim was not found")
    if claim.revision != expected_revision:
        raise SubcontractConflictError("Progress claim changed; refresh before recording payment")
    if claim.status not in {SubcontractClaimStatus.CERTIFIED, SubcontractClaimStatus.PAID}:
        raise SubcontractValidationError("Only certified claims can record operational payment")
    new_paid = money(claim.paid_amount + payment_amount)
    if new_paid > claim.certified_amount:
        raise SubcontractValidationError("Payment cannot exceed the certified claim amount")
    claim.paid_amount = new_paid
    if new_paid == claim.certified_amount:
        claim.status = SubcontractClaimStatus.PAID
    claim.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="subcontracts.claim.payment_recorded",
        target_type="subcontract_claim",
        target_id=str(claim.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"paid_amount": str(claim.paid_amount), "status": claim.status.value},
    )
    await _publish(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="subcontracts.claim.payment_recorded",
        entity_type="subcontract_claim",
        entity_id=claim.id,
        entity_version=claim.revision,
        permission="subcontracts.claim.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return claim
