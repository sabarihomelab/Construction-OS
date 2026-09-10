from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.financials.job_cost_models import CostHeadLedgerMapping
from app.modules.financials.service import FinancialConflictError, FinancialValidationError


async def end_cost_head_ledger_mapping(
    db: AsyncSession,
    *,
    organization_id: UUID,
    mapping_id: UUID,
    expected_revision: int,
    effective_to: date,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> CostHeadLedgerMapping:
    row = await db.scalar(
        select(CostHeadLedgerMapping)
        .where(
            CostHeadLedgerMapping.id == mapping_id,
            CostHeadLedgerMapping.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise FinancialValidationError("Cost Head ledger mapping was not found")
    if row.revision != expected_revision:
        raise FinancialConflictError("Cost Head ledger mapping changed; refresh before saving")
    if effective_to < row.effective_from:
        raise FinancialValidationError("Mapping end date cannot be before its start date")
    if row.effective_to == effective_to:
        return row
    if row.effective_to is not None and effective_to > row.effective_to:
        raise FinancialValidationError(
            "A closed historical mapping cannot be extended; create a new mapping period instead"
        )

    before = row.effective_to
    row.effective_to = effective_to
    row.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.cost_head.mapping.ended",
        target_type="cost_head_ledger_mapping",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={"before": {"effective_to": before}, "after": {"effective_to": effective_to}},
    )
    return row
