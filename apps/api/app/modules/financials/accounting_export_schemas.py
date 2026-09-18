from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.financials.job_cost_models import ProjectCostSourceType
from app.modules.financials.models import JournalSourceType


class AccountingExportAdapter(StrEnum):
    COST_REGISTER_CSV = "cost_register_csv"
    TALLY_PRIME_V1 = "tallyprime_v1"


class AccountingMappingStatus(StrEnum):
    MAPPED = "mapped"
    MISSING = "missing"


class AccountingCostRegisterRow(BaseModel):
    project_cost_entry_id: UUID
    entry_number: str
    entry_date: date
    source_type: ProjectCostSourceType
    source_id: UUID | None
    source_reference: str | None
    allocation_line_number: int
    cost_head_id: UUID
    cost_head_code: str
    cost_head_name: str
    ledger_account_id: UUID | None
    ledger_code: str | None
    ledger_name: str | None
    mapping_status: AccountingMappingStatus
    mapping_effective_from: date | None
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    party_id: UUID | None
    description: str | None
    quantity: Decimal | None
    unit_code: str | None
    amount: Decimal
    currency_code: str


class AccountingCostRegisterExport(BaseModel):
    project_id: UUID
    adapter: AccountingExportAdapter = AccountingExportAdapter.COST_REGISTER_CSV
    from_date: date | None
    to_date: date | None
    currency_code: str
    ready_for_export: bool
    row_count: int
    mapped_row_count: int
    missing_mapping_count: int
    total_amount: Decimal
    rows: list[AccountingCostRegisterRow] = Field(default_factory=list)


class TallyPrimeVoucherLine(BaseModel):
    line_number: int
    ledger_account_id: UUID
    ledger_code: str
    ledger_name: str
    wbs_code_id: UUID | None
    party_id: UUID | None
    description: str | None
    debit_amount: Decimal
    credit_amount: Decimal


class TallyPrimeVoucher(BaseModel):
    journal_entry_id: UUID
    voucher_number: str
    voucher_date: date
    narration: str
    source_type: JournalSourceType
    source_id: UUID | None
    source_reference: str | None
    debit_total: Decimal
    credit_total: Decimal
    lines: list[TallyPrimeVoucherLine] = Field(default_factory=list)


class TallyPrimeExportPreview(BaseModel):
    project_id: UUID
    adapter: AccountingExportAdapter = AccountingExportAdapter.TALLY_PRIME_V1
    from_date: date | None
    to_date: date | None
    ready_for_export: bool
    voucher_count: int
    line_count: int
    vouchers: list[TallyPrimeVoucher] = Field(default_factory=list)
