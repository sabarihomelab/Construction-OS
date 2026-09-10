from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import BOQItem, Party, WBSCode
from app.modules.events.service import enqueue_event
from app.modules.financials.job_cost_models import (
    CostHead,
    CostHeadLedgerMapping,
    ProjectCostAllocation,
    ProjectCostEntry,
    ProjectCostSourceType,
    ProjectCostStatus,
    SiteCashAccount,
    SiteCashAccountStatus,
    SiteCashDirection,
    SiteCashTransaction,
    SiteCashTransactionType,
    SiteExpense,
    SiteExpenseAllocation,
    SiteExpenseStatus,
)
from app.modules.financials.models import FinancialProjectCounter, LedgerAccount, RecordStatus
from app.modules.projects.models import Project, ProjectMembership, ProjectMembershipStatus
from app.modules.workforce.models import ProjectWorkerAssignment, ProjectWorkerAssignmentStatus


class FinancialValidationError(ValueError):
    pass


class FinancialConflictError(FinancialValidationError):
    pass


def _clean_text(value: object, *, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise FinancialValidationError(f"{field} is required")
        return None
    normalized = str(value).strip()
    if required and not normalized:
        raise FinancialValidationError(f"{field} is required")
    return normalized or None


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def _require_project(
    db: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    *,
    lock: bool = False,
) -> Project:
    statement = select(Project).where(
        Project.id == project_id,
        Project.organization_id == organization_id,
    )
    if lock:
        statement = statement.with_for_update()
    project = await db.scalar(statement)
    if project is None:
        raise FinancialValidationError("Project was not found")
    return project


async def _require_project_membership(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    membership = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise FinancialValidationError("An active project membership is required")


async def _next_project_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    kind: str,
    prefix: str,
) -> str:
    await _require_project(db, organization_id, project_id, lock=True)
    counter = await db.scalar(
        select(FinancialProjectCounter)
        .where(
            FinancialProjectCounter.organization_id == organization_id,
            FinancialProjectCounter.project_id == project_id,
            FinancialProjectCounter.kind == kind,
        )
        .with_for_update()
    )
    if counter is None:
        counter = FinancialProjectCounter(
            organization_id=organization_id,
            project_id=project_id,
            kind=kind,
            next_number=2,
        )
        db.add(counter)
        number = 1
    else:
        number = counter.next_number
        counter.next_number += 1
    await db.flush()
    return f"{prefix}-{number:06d}"


async def create_cost_head(
    db: AsyncSession,
    *,
    organization_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> CostHead:
    data = dict(values)
    data["code"] = _clean_text(data.get("code"), field="Cost head code", required=True)
    data["name"] = _clean_text(data.get("name"), field="Cost head name", required=True)
    data["description"] = _clean_text(data.get("description"), field="Description")
    parent_id = data.get("parent_id")
    if parent_id is not None:
        parent = await db.scalar(
            select(CostHead).where(
                CostHead.id == parent_id,
                CostHead.organization_id == organization_id,
            )
        )
        if parent is None:
            raise FinancialValidationError("Parent cost head was not found")
    duplicate = await db.scalar(
        select(CostHead.id).where(
            CostHead.organization_id == organization_id,
            func.lower(CostHead.code) == str(data["code"]).lower(),
        )
    )
    if duplicate is not None:
        raise FinancialConflictError("Cost head code already exists")
    row = CostHead(organization_id=organization_id, **data)
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.cost_head.created",
        target_type="cost_head",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"code": row.code, "name": row.name, "category": row.category.value},
    )
    return row


async def create_ledger_account(
    db: AsyncSession,
    *,
    organization_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> LedgerAccount:
    data = dict(values)
    data["code"] = _clean_text(data.get("code"), field="Ledger code", required=True)
    data["name"] = _clean_text(data.get("name"), field="Ledger name", required=True)
    data["description"] = _clean_text(data.get("description"), field="Description")
    parent_id = data.get("parent_id")
    if parent_id is not None:
        parent = await db.scalar(
            select(LedgerAccount).where(
                LedgerAccount.id == parent_id,
                LedgerAccount.organization_id == organization_id,
            )
        )
        if parent is None:
            raise FinancialValidationError("Parent ledger account was not found")
    duplicate = await db.scalar(
        select(LedgerAccount.id).where(
            LedgerAccount.organization_id == organization_id,
            func.lower(LedgerAccount.code) == str(data["code"]).lower(),
        )
    )
    if duplicate is not None:
        raise FinancialConflictError("Ledger code already exists")
    row = LedgerAccount(organization_id=organization_id, **data)
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.ledger.created",
        target_type="ledger_account",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={"code": row.code, "name": row.name, "account_type": row.account_type.value},
    )
    return row


async def create_cost_head_mapping(
    db: AsyncSession,
    *,
    organization_id: UUID,
    cost_head_id: UUID,
    ledger_account_id: UUID,
    effective_from: date,
    effective_to: date | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> CostHeadLedgerMapping:
    head = await db.scalar(
        select(CostHead).where(
            CostHead.id == cost_head_id,
            CostHead.organization_id == organization_id,
        )
    )
    ledger = await db.scalar(
        select(LedgerAccount).where(
            LedgerAccount.id == ledger_account_id,
            LedgerAccount.organization_id == organization_id,
        )
    )
    if head is None or ledger is None:
        raise FinancialValidationError("Cost head or ledger account was not found")
    if head.status != RecordStatus.ACTIVE or ledger.status != RecordStatus.ACTIVE:
        raise FinancialValidationError("Cost head and ledger account must be active")
    if effective_to is not None and effective_to < effective_from:
        raise FinancialValidationError("Mapping end date cannot be before its start date")
    overlap = await db.scalar(
        select(CostHeadLedgerMapping.id).where(
            CostHeadLedgerMapping.organization_id == organization_id,
            CostHeadLedgerMapping.cost_head_id == cost_head_id,
            CostHeadLedgerMapping.effective_from <= (effective_to or date.max),
            (CostHeadLedgerMapping.effective_to.is_(None))
            | (CostHeadLedgerMapping.effective_to >= effective_from),
        )
    )
    if overlap is not None:
        raise FinancialConflictError("Cost head already has a ledger mapping for this period")
    row = CostHeadLedgerMapping(
        organization_id=organization_id,
        cost_head_id=cost_head_id,
        ledger_account_id=ledger_account_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.cost_head.mapping.created",
        target_type="cost_head_ledger_mapping",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={
            "cost_head_id": str(cost_head_id),
            "ledger_account_id": str(ledger_account_id),
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
    )
    return row


async def create_site_cash_account(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SiteCashAccount:
    project = await _require_project(db, organization_id, project_id)
    data = dict(values)
    data["code"] = _clean_text(data.get("code"), field="Cash account code", required=True)
    data["name"] = _clean_text(data.get("name"), field="Cash account name", required=True)
    data["notes"] = _clean_text(data.get("notes"), field="Notes")
    currency_code = str(data.get("currency_code") or project.currency_code or "INR").upper()
    if project.currency_code and currency_code != project.currency_code.upper():
        raise FinancialValidationError("Site cash currency must match the project currency")
    data["currency_code"] = currency_code

    custodian_worker_id = data.get("custodian_worker_id")
    if custodian_worker_id is not None:
        assignment = await db.scalar(
            select(ProjectWorkerAssignment.id).where(
                ProjectWorkerAssignment.organization_id == organization_id,
                ProjectWorkerAssignment.project_id == project_id,
                ProjectWorkerAssignment.worker_id == custodian_worker_id,
                ProjectWorkerAssignment.status == ProjectWorkerAssignmentStatus.ACTIVE,
            )
        )
        if assignment is None:
            raise FinancialValidationError("Cash custodian Worker must be actively assigned to this project")
    custodian_membership_id = data.get("custodian_membership_id")
    if custodian_membership_id is not None:
        await _require_project_membership(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=UUID(str(custodian_membership_id)),
        )

    duplicate = await db.scalar(
        select(SiteCashAccount.id).where(
            SiteCashAccount.organization_id == organization_id,
            SiteCashAccount.project_id == project_id,
            func.lower(SiteCashAccount.code) == str(data["code"]).lower(),
        )
    )
    if duplicate is not None:
        raise FinancialConflictError("Site cash account code already exists in this project")
    row = SiteCashAccount(organization_id=organization_id, project_id=project_id, **data)
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.site_cash.account.created",
        target_type="site_cash_account",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"project_id": str(project_id), "code": row.code},
    )
    return row


async def _load_cash_account(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    cash_account_id: UUID,
    lock: bool = False,
) -> SiteCashAccount:
    statement = select(SiteCashAccount).where(
        SiteCashAccount.id == cash_account_id,
        SiteCashAccount.organization_id == organization_id,
        SiteCashAccount.project_id == project_id,
    )
    if lock:
        statement = statement.with_for_update()
    row = await db.scalar(statement)
    if row is None:
        raise FinancialValidationError("Site cash account was not found in this project")
    return row


async def site_cash_balance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    cash_account_id: UUID,
) -> tuple[Decimal, Decimal, Decimal]:
    inflow, outflow = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (SiteCashTransaction.direction == SiteCashDirection.INFLOW, SiteCashTransaction.amount),
                            else_=Decimal(0),
                        )
                    ),
                    Decimal(0),
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (SiteCashTransaction.direction == SiteCashDirection.OUTFLOW, SiteCashTransaction.amount),
                            else_=Decimal(0),
                        )
                    ),
                    Decimal(0),
                ),
            ).where(
                SiteCashTransaction.organization_id == organization_id,
                SiteCashTransaction.project_id == project_id,
                SiteCashTransaction.cash_account_id == cash_account_id,
            )
        )
    ).one()
    inflow_amount = _money(inflow)
    outflow_amount = _money(outflow)
    return inflow_amount, outflow_amount, inflow_amount - outflow_amount


async def add_site_cash_advance(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    cash_account_id: UUID,
    amount: Decimal,
    transaction_date: date,
    source_reference: str | None,
    description: str | None,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SiteCashTransaction:
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    account = await _load_cash_account(
        db,
        organization_id=organization_id,
        project_id=project_id,
        cash_account_id=cash_account_id,
        lock=True,
    )
    if account.status != SiteCashAccountStatus.ACTIVE:
        raise FinancialValidationError("Only an active site cash account can receive an advance")
    normalized_amount = _money(amount)
    if normalized_amount <= 0:
        raise FinancialValidationError("Cash advance must be greater than zero")
    number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="site_cash_transaction",
        prefix="CASH",
    )
    row = SiteCashTransaction(
        organization_id=organization_id,
        project_id=project_id,
        cash_account_id=cash_account_id,
        transaction_number=number,
        transaction_date=transaction_date,
        transaction_type=SiteCashTransactionType.ADVANCE,
        direction=SiteCashDirection.INFLOW,
        amount=normalized_amount,
        source_reference=_clean_text(source_reference, field="Source reference"),
        description=_clean_text(description, field="Description"),
        posted_by_membership_id=membership_id,
        posted_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.site_cash.advance.posted",
        target_type="site_cash_transaction",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        changes={"project_id": str(project_id), "cash_account_id": str(cash_account_id), "amount": normalized_amount},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.site_cash.changed",
        entity_type="site_cash_account",
        entity_id=account.id,
        entity_version=account.revision,
        required_permission_key="financials.site_cash.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"transaction_id": str(row.id), "amount": str(normalized_amount), "direction": "inflow"},
    )
    return row


async def _validate_expense_allocations(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    allocations: list[Mapping[str, object]],
    gross_amount: Decimal,
) -> None:
    if not allocations:
        raise FinancialValidationError("At least one site expense allocation is required")
    allocated = sum((_money(item.get("amount", 0)) for item in allocations), Decimal(0))
    if allocated != _money(gross_amount):
        raise FinancialValidationError("Site expense allocation total must equal gross amount")

    for item in allocations:
        cost_head_id = UUID(str(item["cost_head_id"]))
        head = await db.scalar(
            select(CostHead).where(
                CostHead.id == cost_head_id,
                CostHead.organization_id == organization_id,
            )
        )
        if head is None or head.status != RecordStatus.ACTIVE or not head.allows_posting:
            raise FinancialValidationError("Every allocation must use an active posting cost head")

        wbs_code_id = item.get("wbs_code_id")
        wbs = None
        if wbs_code_id is not None:
            wbs = await db.scalar(
                select(WBSCode).where(
                    WBSCode.id == wbs_code_id,
                    WBSCode.organization_id == organization_id,
                    WBSCode.project_id == project_id,
                )
            )
            if wbs is None:
                raise FinancialValidationError("Allocation WBS was not found in this project")

        boq_item_id = item.get("boq_item_id")
        if boq_item_id is not None:
            boq = await db.scalar(
                select(BOQItem).where(
                    BOQItem.id == boq_item_id,
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                )
            )
            if boq is None:
                raise FinancialValidationError("Allocation BOQ item was not found in this project")
            if wbs is not None and boq.wbs_code_id is not None and boq.wbs_code_id != wbs.id:
                raise FinancialValidationError("Allocation BOQ item does not belong to the selected WBS")


async def create_site_expense(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> SiteExpense:
    project = await _require_project(db, organization_id, project_id)
    data = dict(values)
    raw_allocations = list(data.pop("allocations", []))
    gross_amount = _money(data.get("gross_amount", 0))
    if gross_amount <= 0:
        raise FinancialValidationError("Site expense amount must be greater than zero")
    await _validate_expense_allocations(
        db,
        organization_id=organization_id,
        project_id=project_id,
        allocations=raw_allocations,
        gross_amount=gross_amount,
    )
    data["gross_amount"] = gross_amount
    data["description"] = _clean_text(data.get("description"), field="Description", required=True)
    data["notes"] = _clean_text(data.get("notes"), field="Notes")
    currency_code = str(data.get("currency_code") or project.currency_code or "INR").upper()
    if project.currency_code and currency_code != project.currency_code.upper():
        raise FinancialValidationError("Site expense currency must match the project currency")
    data["currency_code"] = currency_code

    cash_account_id = data.get("cash_account_id")
    if cash_account_id is not None:
        cash_account = await _load_cash_account(
            db,
            organization_id=organization_id,
            project_id=project_id,
            cash_account_id=UUID(str(cash_account_id)),
        )
        if cash_account.status != SiteCashAccountStatus.ACTIVE:
            raise FinancialValidationError("Selected site cash account is not active")
        if cash_account.currency_code != currency_code:
            raise FinancialValidationError("Expense and site cash currencies must match")

    paid_to_party_id = data.get("paid_to_party_id")
    if paid_to_party_id is not None:
        party = await db.scalar(
            select(Party.id).where(
                Party.id == paid_to_party_id,
                Party.organization_id == organization_id,
            )
        )
        if party is None:
            raise FinancialValidationError("Paid-to Party was not found")

    number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="site_expense",
        prefix="EXP",
    )
    expense = SiteExpense(
        organization_id=organization_id,
        project_id=project_id,
        expense_number=number,
        **data,
    )
    db.add(expense)
    await db.flush()
    for line_number, raw in enumerate(raw_allocations, start=1):
        item = dict(raw)
        db.add(
            SiteExpenseAllocation(
                organization_id=organization_id,
                project_id=project_id,
                expense_id=expense.id,
                line_number=line_number,
                **item,
            )
        )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.site_expense.created",
        target_type="site_expense",
        target_id=str(expense.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"project_id": str(project_id), "expense_number": expense.expense_number, "gross_amount": gross_amount},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.site_expense.created",
        entity_type="site_expense",
        entity_id=expense.id,
        entity_version=expense.revision,
        required_permission_key="financials.site_expense.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"expense_number": expense.expense_number, "status": expense.status.value},
    )
    return expense


async def _load_expense_for_update(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
    expected_revision: int,
) -> SiteExpense:
    expense = await db.scalar(
        select(SiteExpense)
        .where(
            SiteExpense.id == expense_id,
            SiteExpense.organization_id == organization_id,
            SiteExpense.project_id == project_id,
        )
        .with_for_update()
    )
    if expense is None:
        raise FinancialValidationError("Site expense was not found")
    if expense.revision != expected_revision:
        raise FinancialConflictError("Site expense changed; refresh before continuing")
    return expense


async def _expense_allocations(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
) -> list[SiteExpenseAllocation]:
    rows = await db.scalars(
        select(SiteExpenseAllocation)
        .where(
            SiteExpenseAllocation.organization_id == organization_id,
            SiteExpenseAllocation.project_id == project_id,
            SiteExpenseAllocation.expense_id == expense_id,
        )
        .order_by(SiteExpenseAllocation.line_number)
    )
    return list(rows.all())


async def submit_site_expense(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
    expected_revision: int,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SiteExpense:
    expense = await _load_expense_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        expense_id=expense_id,
        expected_revision=expected_revision,
    )
    if expense.status not in {SiteExpenseStatus.DRAFT, SiteExpenseStatus.REJECTED}:
        raise FinancialValidationError("Only a draft or rejected site expense can be submitted")
    allocations = await _expense_allocations(
        db,
        organization_id=organization_id,
        project_id=project_id,
        expense_id=expense.id,
    )
    await _validate_expense_allocations(
        db,
        organization_id=organization_id,
        project_id=project_id,
        allocations=[
            {
                "cost_head_id": row.cost_head_id,
                "wbs_code_id": row.wbs_code_id,
                "boq_item_id": row.boq_item_id,
                "amount": row.amount,
            }
            for row in allocations
        ],
        gross_amount=expense.gross_amount,
    )
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    now = datetime.now(UTC)
    expense.status = SiteExpenseStatus.SUBMITTED
    expense.submitted_by_membership_id = membership_id
    expense.submitted_at = now
    expense.rejection_reason = None
    expense.configuration_context = {
        "currency_code": expense.currency_code,
        "allocation_count": len(allocations),
        "submitted_at": now.isoformat(),
    }
    expense.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.site_expense.submitted",
        target_type="site_expense",
        target_id=str(expense.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": expense.status.value, "revision": expense.revision},
    )
    return expense


async def review_site_expense(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
    expected_revision: int,
    approve: bool,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SiteExpense:
    expense = await _load_expense_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        expense_id=expense_id,
        expected_revision=expected_revision,
    )
    if expense.status != SiteExpenseStatus.SUBMITTED:
        raise FinancialValidationError("Only a submitted site expense can be approved or rejected")
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    now = datetime.now(UTC)
    if approve:
        expense.status = SiteExpenseStatus.APPROVED
        expense.approved_by_membership_id = membership_id
        expense.approved_at = now
        expense.rejection_reason = None
        action = "financials.site_expense.approved"
    else:
        if not reason or not reason.strip():
            raise FinancialValidationError("A rejection reason is required")
        expense.status = SiteExpenseStatus.REJECTED
        expense.rejection_reason = reason.strip()
        action = "financials.site_expense.rejected"
    expense.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=action,
        target_type="site_expense",
        target_id=str(expense.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": expense.status.value, "revision": expense.revision},
    )
    return expense


async def post_site_expense(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
    expected_revision: int,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> tuple[SiteExpense, ProjectCostEntry]:
    expense = await _load_expense_for_update(
        db,
        organization_id=organization_id,
        project_id=project_id,
        expense_id=expense_id,
        expected_revision=expected_revision,
    )
    if expense.status != SiteExpenseStatus.APPROVED:
        raise FinancialValidationError("Only an approved site expense can be posted")
    await _require_project_membership(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    existing = await db.scalar(
        select(ProjectCostEntry.id).where(
            ProjectCostEntry.organization_id == organization_id,
            ProjectCostEntry.project_id == project_id,
            ProjectCostEntry.source_type == ProjectCostSourceType.SITE_EXPENSE,
            ProjectCostEntry.source_id == expense.id,
        )
    )
    if existing is not None:
        raise FinancialConflictError("This site expense already has a project cost posting")

    allocations = await _expense_allocations(
        db,
        organization_id=organization_id,
        project_id=project_id,
        expense_id=expense.id,
    )
    await _validate_expense_allocations(
        db,
        organization_id=organization_id,
        project_id=project_id,
        allocations=[
            {
                "cost_head_id": row.cost_head_id,
                "wbs_code_id": row.wbs_code_id,
                "boq_item_id": row.boq_item_id,
                "amount": row.amount,
            }
            for row in allocations
        ],
        gross_amount=expense.gross_amount,
    )

    cash_account = None
    if expense.cash_account_id is not None:
        cash_account = await _load_cash_account(
            db,
            organization_id=organization_id,
            project_id=project_id,
            cash_account_id=expense.cash_account_id,
            lock=True,
        )
        if cash_account.status != SiteCashAccountStatus.ACTIVE:
            raise FinancialValidationError("Site cash account is not active")
        _, _, balance = await site_cash_balance(
            db,
            organization_id=organization_id,
            project_id=project_id,
            cash_account_id=cash_account.id,
        )
        if balance < expense.gross_amount:
            raise FinancialValidationError("Site cash account has insufficient available balance")

    now = datetime.now(UTC)
    cost_number = await _next_project_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        kind="project_cost",
        prefix="COST",
    )
    cost = ProjectCostEntry(
        organization_id=organization_id,
        project_id=project_id,
        entry_number=cost_number,
        entry_date=expense.expense_date,
        source_type=ProjectCostSourceType.SITE_EXPENSE,
        source_id=expense.id,
        source_reference=expense.expense_number,
        description=expense.description,
        total_amount=expense.gross_amount,
        currency_code=expense.currency_code,
        status=ProjectCostStatus.POSTED,
        configuration_context=dict(expense.configuration_context),
        revision=1,
        posted_by_membership_id=membership_id,
        posted_at=now,
    )
    db.add(cost)
    await db.flush()
    for line in allocations:
        db.add(
            ProjectCostAllocation(
                organization_id=organization_id,
                project_id=project_id,
                cost_entry_id=cost.id,
                line_number=line.line_number,
                cost_head_id=line.cost_head_id,
                wbs_code_id=line.wbs_code_id,
                boq_item_id=line.boq_item_id,
                party_id=expense.paid_to_party_id,
                description=line.description,
                amount=line.amount,
            )
        )

    if cash_account is not None:
        transaction_number = await _next_project_number(
            db,
            organization_id=organization_id,
            project_id=project_id,
            kind="site_cash_transaction",
            prefix="CASH",
        )
        db.add(
            SiteCashTransaction(
                organization_id=organization_id,
                project_id=project_id,
                cash_account_id=cash_account.id,
                transaction_number=transaction_number,
                transaction_date=expense.expense_date,
                transaction_type=SiteCashTransactionType.EXPENSE,
                direction=SiteCashDirection.OUTFLOW,
                amount=expense.gross_amount,
                source_expense_id=expense.id,
                source_reference=expense.expense_number,
                description=expense.description,
                posted_by_membership_id=membership_id,
                posted_at=now,
            )
        )

    expense.status = SiteExpenseStatus.POSTED
    expense.posted_by_membership_id = membership_id
    expense.posted_at = now
    expense.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="financials.site_expense.posted",
        target_type="site_expense",
        target_id=str(expense.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "project_cost_entry_id": str(cost.id),
            "amount": expense.gross_amount,
            "cash_account_id": str(expense.cash_account_id) if expense.cash_account_id else None,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="financials.project_cost.posted",
        entity_type="project_cost_entry",
        entity_id=cost.id,
        entity_version=cost.revision,
        required_permission_key="financials.project_cost.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"source_type": cost.source_type.value, "source_id": str(expense.id), "amount": str(cost.total_amount)},
    )
    return expense, cost


async def job_cost_summary_rows(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[tuple[CostHead, Decimal]]:
    rows = await db.execute(
        select(CostHead, func.sum(ProjectCostAllocation.amount))
        .join(ProjectCostAllocation, ProjectCostAllocation.cost_head_id == CostHead.id)
        .join(ProjectCostEntry, ProjectCostEntry.id == ProjectCostAllocation.cost_entry_id)
        .where(
            ProjectCostEntry.organization_id == organization_id,
            ProjectCostEntry.project_id == project_id,
            ProjectCostEntry.status == ProjectCostStatus.POSTED,
            ProjectCostAllocation.organization_id == organization_id,
            ProjectCostAllocation.project_id == project_id,
        )
        .group_by(CostHead.id)
        .order_by(CostHead.code)
    )
    return [(head, _money(amount)) for head, amount in rows.all()]
