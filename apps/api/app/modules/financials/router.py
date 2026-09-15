from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.financials.job_cost_models import (
    CostHead,
    ProjectCostEntry,
    SiteCashAccount,
    SiteCashTransaction,
    SiteExpense,
    SiteExpenseAllocation,
)
from app.modules.financials.models import LedgerAccount
from app.modules.financials.schemas import (
    CostHeadCreate,
    CostHeadRead,
    JobCostSummaryLine,
    JobCostSummaryRead,
    LedgerAccountCreate,
    LedgerAccountRead,
    ProjectCostRead,
    RejectAction,
    RevisionAction,
    SiteCashAccountCreate,
    SiteCashAccountRead,
    SiteCashAdvanceCreate,
    SiteCashBalanceRead,
    SiteCashTransactionRead,
    SiteExpenseAllocationRead,
    SiteExpenseCreate,
    SiteExpenseDetailRead,
    SiteExpenseRead,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    add_site_cash_advance,
    create_cost_head,
    create_ledger_account,
    create_site_cash_account,
    create_site_expense,
    job_cost_summary_rows,
    post_site_expense,
    review_site_expense,
    site_cash_balance,
    submit_site_expense,
)
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _require_org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(values) for key, values in context.project_permissions.items()},
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, FinancialConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/financials/cost-heads", response_model=list[CostHeadRead])
async def list_company_cost_heads(db: DbSession, session: CurrentSession) -> list[CostHead]:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.cost_head.view")
    rows = await db.scalars(
        select(CostHead)
        .where(CostHead.organization_id == context.organization_id)
        .order_by(CostHead.code)
    )
    return list(rows.all())


@router.post(
    "/financials/cost-heads",
    response_model=CostHeadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_cost_head(
    payload: CostHeadCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> CostHead:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.cost_head.manage")
    try:
        row = await create_cost_head(
            db,
            organization_id=context.organization_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/financials/cost-heads",
    response_model=list[CostHeadRead],
)
async def list_project_available_cost_heads(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[CostHead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.cost_head.view")
    rows = await db.scalars(
        select(CostHead)
        .where(CostHead.organization_id == context.organization_id)
        .order_by(CostHead.code)
    )
    return list(rows.all())


@router.get("/financials/ledger-accounts", response_model=list[LedgerAccountRead])
async def list_ledger_accounts(db: DbSession, session: CurrentSession) -> list[LedgerAccount]:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.ledger.view")
    rows = await db.scalars(
        select(LedgerAccount)
        .where(LedgerAccount.organization_id == context.organization_id)
        .order_by(LedgerAccount.code)
    )
    return list(rows.all())


@router.post(
    "/financials/ledger-accounts",
    response_model=LedgerAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_ledger_account(
    payload: LedgerAccountCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> LedgerAccount:
    context = await build_access_context(db, session.membership_id)
    _require_org_permission(context, "financials.ledger.manage")
    try:
        row = await create_ledger_account(
            db,
            organization_id=context.organization_id,
            values=payload.model_dump(),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/financials/site-cash",
    response_model=list[SiteCashAccountRead],
)
async def list_site_cash_accounts(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SiteCashAccount]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_cash.view")
    rows = await db.scalars(
        select(SiteCashAccount)
        .where(
            SiteCashAccount.organization_id == context.organization_id,
            SiteCashAccount.project_id == project_id,
        )
        .order_by(SiteCashAccount.code)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/financials/site-cash",
    response_model=SiteCashAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_site_cash_account(
    project_id: UUID,
    payload: SiteCashAccountCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteCashAccount:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_cash.manage")
    try:
        row = await create_site_cash_account(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
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
    "/projects/{project_id}/financials/site-cash/{cash_account_id}/advances",
    response_model=SiteCashTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_site_cash_advance(
    project_id: UUID,
    cash_account_id: UUID,
    payload: SiteCashAdvanceCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteCashTransaction:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_cash.manage")
    try:
        row = await add_site_cash_advance(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            cash_account_id=cash_account_id,
            amount=payload.amount,
            transaction_date=payload.transaction_date,
            source_reference=payload.source_reference,
            description=payload.description,
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/financials/site-cash/{cash_account_id}/balance",
    response_model=SiteCashBalanceRead,
)
async def get_site_cash_balance(
    project_id: UUID,
    cash_account_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> SiteCashBalanceRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_cash.view")
    account = await db.scalar(
        select(SiteCashAccount).where(
            SiteCashAccount.id == cash_account_id,
            SiteCashAccount.organization_id == context.organization_id,
            SiteCashAccount.project_id == project_id,
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site cash account not found")
    inflow, outflow, balance = await site_cash_balance(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        cash_account_id=cash_account_id,
    )
    return SiteCashBalanceRead(
        cash_account_id=cash_account_id,
        currency_code=account.currency_code,
        inflow=inflow,
        outflow=outflow,
        balance=balance,
    )


@router.get(
    "/projects/{project_id}/financials/site-cash/{cash_account_id}/transactions",
    response_model=list[SiteCashTransactionRead],
)
async def list_site_cash_transactions(
    project_id: UUID,
    cash_account_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SiteCashTransaction]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_cash.view")
    rows = await db.scalars(
        select(SiteCashTransaction)
        .where(
            SiteCashTransaction.organization_id == context.organization_id,
            SiteCashTransaction.project_id == project_id,
            SiteCashTransaction.cash_account_id == cash_account_id,
        )
        .order_by(SiteCashTransaction.transaction_date.desc(), SiteCashTransaction.created_at.desc())
    )
    return list(rows.all())


async def _expense_detail(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense: SiteExpense,
) -> SiteExpenseDetailRead:
    allocations = list(
        (
            await db.scalars(
                select(SiteExpenseAllocation)
                .where(
                    SiteExpenseAllocation.organization_id == organization_id,
                    SiteExpenseAllocation.project_id == project_id,
                    SiteExpenseAllocation.expense_id == expense.id,
                )
                .order_by(SiteExpenseAllocation.line_number)
            )
        ).all()
    )
    return SiteExpenseDetailRead(
        **SiteExpenseRead.model_validate(expense).model_dump(),
        allocations=[SiteExpenseAllocationRead.model_validate(item) for item in allocations],
    )


@router.get(
    "/projects/{project_id}/financials/site-expenses",
    response_model=list[SiteExpenseRead],
)
async def list_site_expenses(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SiteExpense]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.view")
    rows = await db.scalars(
        select(SiteExpense)
        .where(
            SiteExpense.organization_id == context.organization_id,
            SiteExpense.project_id == project_id,
        )
        .order_by(SiteExpense.expense_date.desc(), SiteExpense.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/financials/site-expenses",
    response_model=SiteExpenseDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_site_expense(
    project_id: UUID,
    payload: SiteExpenseCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteExpenseDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.create")
    try:
        row = await create_site_expense(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            values=payload.model_dump(),
            membership_id=context.membership_id,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(row)
        return await _expense_detail(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            expense=row,
        )
    except (FinancialConflictError, FinancialValidationError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/projects/{project_id}/financials/site-expenses/{expense_id}",
    response_model=SiteExpenseDetailRead,
)
async def get_site_expense(
    project_id: UUID,
    expense_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> SiteExpenseDetailRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.view")
    row = await db.scalar(
        select(SiteExpense).where(
            SiteExpense.id == expense_id,
            SiteExpense.organization_id == context.organization_id,
            SiteExpense.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site expense not found")
    return await _expense_detail(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        expense=row,
    )


@router.post(
    "/projects/{project_id}/financials/site-expenses/{expense_id}/submit",
    response_model=SiteExpenseRead,
)
async def submit_project_site_expense(
    project_id: UUID,
    expense_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteExpense:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.create")
    try:
        row = await submit_site_expense(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            expense_id=expense_id,
            expected_revision=payload.expected_revision,
            membership_id=context.membership_id,
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


@router.post(
    "/projects/{project_id}/financials/site-expenses/{expense_id}/approve",
    response_model=SiteExpenseRead,
)
async def approve_project_site_expense(
    project_id: UUID,
    expense_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteExpense:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.approve")
    try:
        row = await review_site_expense(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            expense_id=expense_id,
            expected_revision=payload.expected_revision,
            approve=True,
            membership_id=context.membership_id,
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


@router.post(
    "/projects/{project_id}/financials/site-expenses/{expense_id}/reject",
    response_model=SiteExpenseRead,
)
async def reject_project_site_expense(
    project_id: UUID,
    expense_id: UUID,
    payload: RejectAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteExpense:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.approve")
    try:
        row = await review_site_expense(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            expense_id=expense_id,
            expected_revision=payload.expected_revision,
            approve=False,
            membership_id=context.membership_id,
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


@router.post(
    "/projects/{project_id}/financials/site-expenses/{expense_id}/post",
    response_model=SiteExpenseRead,
)
async def post_project_site_expense(
    project_id: UUID,
    expense_id: UUID,
    payload: RevisionAction,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> SiteExpense:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.post")
    try:
        row, _ = await post_site_expense(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            expense_id=expense_id,
            expected_revision=payload.expected_revision,
            membership_id=context.membership_id,
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


@router.get(
    "/projects/{project_id}/financials/job-cost/entries",
    response_model=list[ProjectCostRead],
)
async def list_project_cost_entries(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[ProjectCostEntry]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.project_cost.view")
    rows = await db.scalars(
        select(ProjectCostEntry)
        .where(
            ProjectCostEntry.organization_id == context.organization_id,
            ProjectCostEntry.project_id == project_id,
        )
        .order_by(ProjectCostEntry.entry_date.desc(), ProjectCostEntry.created_at.desc())
    )
    return list(rows.all())


@router.get(
    "/projects/{project_id}/financials/job-cost/summary",
    response_model=JobCostSummaryRead,
)
async def get_project_job_cost_summary(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> JobCostSummaryRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.project_cost.view")
    rows = await job_cost_summary_rows(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
    )
    lines = [
        JobCostSummaryLine(
            cost_head_id=head.id,
            cost_head_code=head.code,
            cost_head_name=head.name,
            category=head.category,
            amount=amount,
        )
        for head, amount in rows
    ]
    total = sum((line.amount for line in lines), start=0)
    project_cash = await db.scalar(
        select(SiteCashAccount.currency_code).where(
            SiteCashAccount.organization_id == context.organization_id,
            SiteCashAccount.project_id == project_id,
        )
    )
    return JobCostSummaryRead(
        project_id=project_id,
        currency_code=project_cash or "INR",
        total_actual_cost=total,
        by_cost_head=lines,
    )
