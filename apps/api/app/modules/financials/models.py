from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class JournalStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


class JournalSourceType(StrEnum):
    MANUAL = "manual"
    PURCHASE_ORDER = "purchase_order"
    GOODS_RECEIPT = "goods_receipt"
    SUBCONTRACT_CLAIM = "subcontract_claim"
    WORKFORCE = "workforce"
    EQUIPMENT = "equipment"
    CLIENT_INVOICE = "client_invoice"
    CLIENT_RECEIPT = "client_receipt"
    ADJUSTMENT = "adjustment"


class CommitmentSourceType(StrEnum):
    PURCHASE_ORDER = "purchase_order"
    SUBCONTRACT = "subcontract"


class CommitmentStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ClientInvoiceStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class ClientReceiptStatus(StrEnum):
    POSTED = "posted"
    REVERSED = "reversed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class FinancialProjectCounter(Base):
    __tablename__ = "financial_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_financial_project_counters_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", "kind", name="uq_financial_project_counter_kind"),
        CheckConstraint("next_number >= 1", name="ck_financial_project_counter_next_number"),
    )

    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1)


class LedgerAccount(UUIDTimestampMixin, Base):
    __tablename__ = "ledger_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_ledger_accounts_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id", "organization_id"],
            ["ledger_accounts.id", "ledger_accounts.organization_id"],
            name="fk_ledger_accounts_parent_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "code", name="uq_ledger_accounts_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_ledger_accounts_id_org"),
        CheckConstraint("revision >= 1", name="ck_ledger_accounts_revision"),
        Index("ix_ledger_accounts_org_type_status", "organization_id", "account_type", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, native_enum=False, values_callable=enum_values),
        default=RecordStatus.ACTIVE,
    )
    allows_posting: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalEntry(UUIDTimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_journal_entries_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["posted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_journal_entries_posted_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reversed_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_journal_entries_reversed_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reversal_of_entry_id", "organization_id"],
            ["journal_entries.id", "journal_entries.organization_id"],
            name="fk_journal_entries_reversal_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "entry_number", name="uq_journal_entries_org_number"),
        UniqueConstraint("id", "organization_id", name="uq_journal_entries_id_org"),
        CheckConstraint("revision >= 1", name="ck_journal_entries_revision"),
        Index("ix_journal_entries_org_date_status", "organization_id", "entry_date", "status"),
        Index("ix_journal_entries_project_date", "project_id", "entry_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    entry_number: Mapped[str] = mapped_column(String(80))
    entry_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[JournalSourceType] = mapped_column(
        Enum(JournalSourceType, native_enum=False, values_callable=enum_values),
        default=JournalSourceType.MANUAL,
    )
    source_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[JournalStatus] = mapped_column(
        Enum(JournalStatus, native_enum=False, values_callable=enum_values),
        default=JournalStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    posted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_of_entry_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalLine(UUIDTimestampMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["journal_entry_id", "organization_id"],
            ["journal_entries.id", "journal_entries.organization_id"],
            name="fk_journal_lines_entry_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["account_id", "organization_id"],
            ["ledger_accounts.id", "ledger_accounts.organization_id"],
            name="fk_journal_lines_account_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_journal_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_journal_lines_party_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_lines_number"),
        CheckConstraint("debit_amount >= 0", name="ck_journal_lines_debit_nonnegative"),
        CheckConstraint("credit_amount >= 0", name="ck_journal_lines_credit_nonnegative"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_journal_lines_one_sided",
        ),
        Index("ix_journal_lines_project_wbs", "project_id", "wbs_code_id"),
        Index("ix_journal_lines_account", "account_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    journal_entry_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    party_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))


class ProjectCommitment(UUIDTimestampMixin, Base):
    __tablename__ = "project_commitments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_commitments_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_project_commitments_party_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_project_commitments_wbs_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "source_type",
            "source_id",
            name="uq_project_commitments_source",
        ),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_project_commitments_scope"),
        CheckConstraint("committed_amount >= 0", name="ck_project_commitments_amount"),
        CheckConstraint("revision >= 1", name="ck_project_commitments_revision"),
        Index("ix_project_commitments_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_type: Mapped[CommitmentSourceType] = mapped_column(
        Enum(CommitmentSourceType, native_enum=False, values_callable=enum_values)
    )
    source_id: Mapped[UUID] = mapped_column(Uuid)
    source_number: Mapped[str] = mapped_column(String(80))
    party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(CommitmentStatus, native_enum=False, values_callable=enum_values),
        default=CommitmentStatus.OPEN,
    )
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ClientInvoice(UUIDTimestampMixin, Base):
    __tablename__ = "client_invoices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_client_invoices_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["client_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_client_invoices_party_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_ra_bill_id", "project_id", "organization_id"],
            ["ra_bills.id", "ra_bills.project_id", "ra_bills.organization_id"],
            name="fk_client_invoices_ra_bill_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_client_invoices_approved_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "invoice_number", name="uq_client_invoices_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_client_invoices_scope"),
        CheckConstraint("subtotal >= 0", name="ck_client_invoices_subtotal"),
        CheckConstraint("tax_amount >= 0", name="ck_client_invoices_tax"),
        CheckConstraint("withholding_amount >= 0", name="ck_client_invoices_withholding"),
        CheckConstraint("total_amount >= 0", name="ck_client_invoices_total"),
        CheckConstraint("net_receivable >= 0", name="ck_client_invoices_net_receivable"),
        CheckConstraint("revision >= 1", name="ck_client_invoices_revision"),
        Index("ix_client_invoices_project_status", "project_id", "status", "invoice_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invoice_number: Mapped[str] = mapped_column(String(80))
    client_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_ra_bill_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    withholding_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    net_receivable: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    status: Mapped[ClientInvoiceStatus] = mapped_column(
        Enum(ClientInvoiceStatus, native_enum=False, values_callable=enum_values),
        default=ClientInvoiceStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClientInvoiceLine(UUIDTimestampMixin, Base):
    __tablename__ = "client_invoice_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "project_id", "organization_id"],
            ["client_invoices.id", "client_invoices.project_id", "client_invoices.organization_id"],
            name="fk_client_invoice_lines_invoice_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_client_invoice_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_client_invoice_lines_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("invoice_id", "line_number", name="uq_client_invoice_lines_number"),
        CheckConstraint("quantity >= 0", name="ck_client_invoice_lines_quantity"),
        CheckConstraint("rate >= 0", name="ck_client_invoice_lines_rate"),
        CheckConstraint("amount >= 0", name="ck_client_invoice_lines_amount"),
        CheckConstraint("tax_rate >= 0", name="ck_client_invoice_lines_tax_rate"),
        CheckConstraint("tax_amount >= 0", name="ck_client_invoice_lines_tax_amount"),
        Index("ix_client_invoice_lines_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invoice_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    hsn_sac: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal(0))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))


class ClientReceipt(UUIDTimestampMixin, Base):
    __tablename__ = "client_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_client_receipts_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["client_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_client_receipts_party_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["posted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_client_receipts_posted_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reversal_of_receipt_id", "organization_id"],
            ["client_receipts.id", "client_receipts.organization_id"],
            name="fk_client_receipts_reversal_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "receipt_number", name="uq_client_receipts_project_number"),
        UniqueConstraint("id", "organization_id", name="uq_client_receipts_id_org"),
        CheckConstraint("amount > 0", name="ck_client_receipts_amount"),
        Index("ix_client_receipts_project_date", "project_id", "receipt_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    receipt_number: Mapped[str] = mapped_column(String(80))
    client_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    receipt_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    payment_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[ClientReceiptStatus] = mapped_column(
        Enum(ClientReceiptStatus, native_enum=False, values_callable=enum_values),
        default=ClientReceiptStatus.POSTED,
    )
    posted_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reversal_of_receipt_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClientReceiptAllocation(UUIDTimestampMixin, Base):
    __tablename__ = "client_receipt_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["receipt_id", "organization_id"],
            ["client_receipts.id", "client_receipts.organization_id"],
            name="fk_client_receipt_allocations_receipt_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["invoice_id", "project_id", "organization_id"],
            ["client_invoices.id", "client_invoices.project_id", "client_invoices.organization_id"],
            name="fk_client_receipt_allocations_invoice_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("receipt_id", "invoice_id", name="uq_client_receipt_allocation_invoice"),
        CheckConstraint("amount > 0", name="ck_client_receipt_allocations_amount"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    receipt_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invoice_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
