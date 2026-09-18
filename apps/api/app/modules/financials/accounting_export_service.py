import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from io import StringIO
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.financials.accounting_export_schemas import (
    AccountingCostRegisterExport,
    AccountingCostRegisterRow,
    AccountingMappingStatus,
    TallyPrimeExportPreview,
    TallyPrimeVoucher,
    TallyPrimeVoucherLine,
)
from app.modules.financials.job_cost_models import (
    CostHead,
    CostHeadLedgerMapping,
    ProjectCostAllocation,
    ProjectCostEntry,
    ProjectCostStatus,
)
from app.modules.financials.models import (
    JournalEntry,
    JournalLine,
    JournalStatus,
    LedgerAccount,
)
from app.modules.financials.service import (
    FinancialConflictError,
    FinancialValidationError,
    _require_project,
)


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _validate_date_range(from_date: date | None, to_date: date | None) -> None:
    if from_date is not None and to_date is not None and to_date < from_date:
        raise FinancialValidationError("Accounting export end date cannot be before start date")


async def build_cost_register_export(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
) -> AccountingCostRegisterExport:
    _validate_date_range(from_date, to_date)
    project = await _require_project(db, organization_id, project_id)
    currency_code = (project.currency_code or "INR").upper()

    statement = (
        select(ProjectCostEntry, ProjectCostAllocation, CostHead)
        .join(
            ProjectCostAllocation,
            ProjectCostAllocation.cost_entry_id == ProjectCostEntry.id,
        )
        .join(CostHead, CostHead.id == ProjectCostAllocation.cost_head_id)
        .where(
            ProjectCostEntry.organization_id == organization_id,
            ProjectCostEntry.project_id == project_id,
            ProjectCostEntry.status.in_(
                {ProjectCostStatus.POSTED, ProjectCostStatus.REVERSED}
            ),
            ProjectCostAllocation.organization_id == organization_id,
            ProjectCostAllocation.project_id == project_id,
            CostHead.organization_id == organization_id,
        )
        .order_by(
            ProjectCostEntry.entry_date,
            ProjectCostEntry.entry_number,
            ProjectCostAllocation.line_number,
        )
    )
    if from_date is not None:
        statement = statement.where(ProjectCostEntry.entry_date >= from_date)
    if to_date is not None:
        statement = statement.where(ProjectCostEntry.entry_date <= to_date)

    source_rows = list((await db.execute(statement)).all())
    cost_head_ids = {allocation.cost_head_id for _, allocation, _ in source_rows}
    mappings: list[CostHeadLedgerMapping] = []
    if cost_head_ids:
        mapping_statement = select(CostHeadLedgerMapping).where(
            CostHeadLedgerMapping.organization_id == organization_id,
            CostHeadLedgerMapping.cost_head_id.in_(cost_head_ids),
        )
        if to_date is not None:
            mapping_statement = mapping_statement.where(
                CostHeadLedgerMapping.effective_from <= to_date
            )
        if from_date is not None:
            mapping_statement = mapping_statement.where(
                or_(
                    CostHeadLedgerMapping.effective_to.is_(None),
                    CostHeadLedgerMapping.effective_to >= from_date,
                )
            )
        mappings = list((await db.scalars(mapping_statement)).all())

    ledger_ids = {mapping.ledger_account_id for mapping in mappings}
    ledgers = {}
    if ledger_ids:
        ledgers = {
            ledger.id: ledger
            for ledger in (
                await db.scalars(
                    select(LedgerAccount).where(
                        LedgerAccount.organization_id == organization_id,
                        LedgerAccount.id.in_(ledger_ids),
                    )
                )
            ).all()
        }

    by_cost_head: dict[UUID, list[CostHeadLedgerMapping]] = defaultdict(list)
    for mapping in mappings:
        by_cost_head[mapping.cost_head_id].append(mapping)

    rows: list[AccountingCostRegisterRow] = []
    missing_mapping_count = 0
    for entry, allocation, cost_head in source_rows:
        if entry.currency_code.upper() != currency_code:
            raise FinancialConflictError(
                "Posted project cost currency does not match project currency"
            )

        effective = [
            mapping
            for mapping in by_cost_head.get(allocation.cost_head_id, [])
            if mapping.effective_from <= entry.entry_date
            and (mapping.effective_to is None or mapping.effective_to >= entry.entry_date)
        ]
        if len(effective) > 1:
            raise FinancialConflictError(
                f"Cost head {cost_head.code} has overlapping ledger mappings"
            )

        mapping = effective[0] if effective else None
        ledger = ledgers.get(mapping.ledger_account_id) if mapping is not None else None
        if mapping is not None and ledger is None:
            raise FinancialConflictError(
                f"Mapped ledger account was not found for cost head {cost_head.code}"
            )
        if mapping is None:
            missing_mapping_count += 1

        rows.append(
            AccountingCostRegisterRow(
                project_cost_entry_id=entry.id,
                entry_number=entry.entry_number,
                entry_date=entry.entry_date,
                source_type=entry.source_type,
                source_id=entry.source_id,
                source_reference=entry.source_reference,
                allocation_line_number=allocation.line_number,
                cost_head_id=cost_head.id,
                cost_head_code=cost_head.code,
                cost_head_name=cost_head.name,
                ledger_account_id=ledger.id if ledger is not None else None,
                ledger_code=ledger.code if ledger is not None else None,
                ledger_name=ledger.name if ledger is not None else None,
                mapping_status=(
                    AccountingMappingStatus.MAPPED
                    if mapping is not None
                    else AccountingMappingStatus.MISSING
                ),
                mapping_effective_from=(
                    mapping.effective_from if mapping is not None else None
                ),
                wbs_code_id=allocation.wbs_code_id,
                boq_item_id=allocation.boq_item_id,
                party_id=allocation.party_id,
                description=allocation.description or entry.description,
                quantity=allocation.quantity,
                unit_code=allocation.unit_code,
                amount=(
                    -_money(allocation.amount)
                    if entry.reversal_of_entry_id is not None
                    else _money(allocation.amount)
                ),
                currency_code=entry.currency_code.upper(),
            )
        )

    total_amount = _money(sum((row.amount for row in rows), start=Decimal(0)))
    return AccountingCostRegisterExport(
        project_id=project_id,
        from_date=from_date,
        to_date=to_date,
        currency_code=currency_code,
        ready_for_export=missing_mapping_count == 0,
        row_count=len(rows),
        mapped_row_count=len(rows) - missing_mapping_count,
        missing_mapping_count=missing_mapping_count,
        total_amount=total_amount,
        rows=rows,
    )


def serialize_cost_register_csv(export: AccountingCostRegisterExport) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "entry_number",
            "entry_date",
            "source_type",
            "source_reference",
            "allocation_line_number",
            "cost_head_code",
            "cost_head_name",
            "ledger_code",
            "ledger_name",
            "mapping_status",
            "wbs_code_id",
            "boq_item_id",
            "party_id",
            "description",
            "quantity",
            "unit_code",
            "amount",
            "currency_code",
        ]
    )
    for row in export.rows:
        writer.writerow(
            [
                row.entry_number,
                row.entry_date.isoformat(),
                row.source_type.value,
                row.source_reference or "",
                row.allocation_line_number,
                row.cost_head_code,
                row.cost_head_name,
                row.ledger_code or "",
                row.ledger_name or "",
                row.mapping_status.value,
                str(row.wbs_code_id or ""),
                str(row.boq_item_id or ""),
                str(row.party_id or ""),
                row.description or "",
                str(row.quantity) if row.quantity is not None else "",
                row.unit_code or "",
                str(row.amount),
                row.currency_code,
            ]
        )
    return output.getvalue()


async def build_tallyprime_preview(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
) -> TallyPrimeExportPreview:
    _validate_date_range(from_date, to_date)
    await _require_project(db, organization_id, project_id)

    statement = (
        select(JournalEntry, JournalLine, LedgerAccount)
        .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
        .join(LedgerAccount, LedgerAccount.id == JournalLine.account_id)
        .where(
            JournalEntry.organization_id == organization_id,
            JournalEntry.project_id == project_id,
            JournalEntry.status == JournalStatus.POSTED,
            JournalLine.organization_id == organization_id,
            JournalLine.project_id == project_id,
            LedgerAccount.organization_id == organization_id,
        )
        .order_by(
            JournalEntry.entry_date,
            JournalEntry.entry_number,
            JournalLine.line_number,
        )
    )
    if from_date is not None:
        statement = statement.where(JournalEntry.entry_date >= from_date)
    if to_date is not None:
        statement = statement.where(JournalEntry.entry_date <= to_date)

    source_rows = list((await db.execute(statement)).all())
    grouped: dict[UUID, list[tuple[JournalEntry, JournalLine, LedgerAccount]]] = defaultdict(list)
    for entry, line, ledger in source_rows:
        grouped[entry.id].append((entry, line, ledger))

    vouchers: list[TallyPrimeVoucher] = []
    total_lines = 0
    for grouped_rows in grouped.values():
        entry = grouped_rows[0][0]
        lines = [
            TallyPrimeVoucherLine(
                line_number=line.line_number,
                ledger_account_id=ledger.id,
                ledger_code=ledger.code,
                ledger_name=ledger.name,
                wbs_code_id=line.wbs_code_id,
                party_id=line.party_id,
                description=line.description,
                debit_amount=_money(line.debit_amount),
                credit_amount=_money(line.credit_amount),
            )
            for _, line, ledger in grouped_rows
        ]
        debit_total = _money(sum((line.debit_amount for line in lines), start=Decimal(0)))
        credit_total = _money(sum((line.credit_amount for line in lines), start=Decimal(0)))
        if not lines or debit_total != credit_total:
            raise FinancialConflictError(
                f"Posted journal {entry.entry_number} is not balanced for TallyPrime export"
            )
        total_lines += len(lines)
        vouchers.append(
            TallyPrimeVoucher(
                journal_entry_id=entry.id,
                voucher_number=entry.entry_number,
                voucher_date=entry.entry_date,
                narration=entry.description,
                source_type=entry.source_type,
                source_id=entry.source_id,
                source_reference=entry.source_reference,
                debit_total=debit_total,
                credit_total=credit_total,
                lines=lines,
            )
        )

    return TallyPrimeExportPreview(
        project_id=project_id,
        from_date=from_date,
        to_date=to_date,
        ready_for_export=True,
        voucher_count=len(vouchers),
        line_count=total_lines,
        vouchers=vouchers,
    )
