from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.governed_receivable_schemas import GovernedClientInvoiceFromRABillCreate
from app.modules.financials.governed_receivable_service import (
    create_governed_client_invoice_from_ra_bill,
)
from app.modules.financials.models import ClientInvoice
from app.modules.financials.receivable_router import _invoice_detail
from app.modules.financials.receivable_schemas import ClientInvoiceDetailRead
from app.modules.financials.rule_models import FinancialRuleSnapshot
from app.modules.financials.service import FinancialConflictError, FinancialValidationError
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.post(
    "/projects/{project_id}/financials/receivables/invoices/from-ra-bill",
    response_model=ClientInvoiceDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_governed_client_invoice_from_ra_bill_route(
    project_id: UUID,
    payload: GovernedClientInvoiceFromRABillCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientInvoiceDetailRead:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.manage")
    try:
        invoice = await create_governed_client_invoice_from_ra_bill(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(invoice)
        return await _invoice_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            invoice=invoice,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        status_code = (
            status.HTTP_409_CONFLICT
            if isinstance(exc, FinancialConflictError)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/financials/receivables/invoices/{invoice_id}/rule-snapshots",
)
async def list_client_invoice_rule_snapshots(
    project_id: UUID,
    invoice_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[dict[str, object]]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "financials.receivable.view")
    invoice = await db.scalar(
        select(ClientInvoice.id).where(
            ClientInvoice.id == invoice_id,
            ClientInvoice.organization_id == context.organization_id,
            ClientInvoice.project_id == project_id,
        )
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client invoice not found")
    rows = list(
        (
            await db.scalars(
                select(FinancialRuleSnapshot)
                .where(
                    FinancialRuleSnapshot.organization_id == context.organization_id,
                    FinancialRuleSnapshot.project_id == project_id,
                    FinancialRuleSnapshot.entity_type == "client_invoice",
                    FinancialRuleSnapshot.entity_id == invoice_id,
                )
                .order_by(FinancialRuleSnapshot.rule_key)
            )
        ).all()
    )
    return [
        {
            "rule_key": row.rule_key,
            "source": row.source,
            "version": row.version,
            "effective_from": row.effective_from,
            "applied_at": row.applied_at,
            "snapshot": row.snapshot_json,
        }
        for row in rows
    ]
