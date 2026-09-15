from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.job_cost_models import CostHeadLedgerMapping
from app.modules.financials.mapping_schemas import (
    CostHeadLedgerMappingEnd,
    CostHeadLedgerMappingRead,
)
from app.modules.financials.mapping_service import end_cost_head_ledger_mapping
from app.modules.financials.schemas import CostHeadLedgerMappingCreate
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    create_cost_head_mapping,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _require_org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, FinancialConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/financials/cost-heads/{cost_head_id}/ledger-mappings",
    response_model=list[CostHeadLedgerMappingRead],
)
async def list_cost_head_ledger_mappings(
    cost_head_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[CostHeadLedgerMapping]:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.cost_head.view")
    rows = await db.scalars(
        select(CostHeadLedgerMapping)
        .where(
            CostHeadLedgerMapping.organization_id == context.organization_id,
            CostHeadLedgerMapping.cost_head_id == cost_head_id,
        )
        .order_by(CostHeadLedgerMapping.effective_from.desc())
    )
    return list(rows.all())


@router.post(
    "/financials/cost-heads/{cost_head_id}/ledger-mappings",
    response_model=CostHeadLedgerMappingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_cost_head_ledger_mapping_route(
    cost_head_id: UUID,
    payload: CostHeadLedgerMappingCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> CostHeadLedgerMapping:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.cost_head.manage")
    try:
        row = await create_cost_head_mapping(
            db,
            organization_id=context.organization_id,
            cost_head_id=cost_head_id,
            ledger_account_id=payload.ledger_account_id,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/financials/cost-heads/{cost_head_id}/ledger-mappings/{mapping_id}/end",
    response_model=CostHeadLedgerMappingRead,
)
async def end_cost_head_ledger_mapping_route(
    cost_head_id: UUID,
    mapping_id: UUID,
    payload: CostHeadLedgerMappingEnd,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> CostHeadLedgerMapping:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.cost_head.manage")
    try:
        row = await db.scalar(
            select(CostHeadLedgerMapping).where(
                CostHeadLedgerMapping.id == mapping_id,
                CostHeadLedgerMapping.organization_id == context.organization_id,
                CostHeadLedgerMapping.cost_head_id == cost_head_id,
            )
        )
        if row is None:
            raise FinancialValidationError("Cost Head ledger mapping was not found")
        row = await end_cost_head_ledger_mapping(
            db,
            organization_id=context.organization_id,
            mapping_id=mapping_id,
            expected_revision=payload.expected_revision,
            effective_to=payload.effective_to,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)
