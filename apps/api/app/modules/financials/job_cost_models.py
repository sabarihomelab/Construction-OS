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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin
from app.modules.financials.models import RecordStatus


class CostHeadCategory(StrEnum):
    MATERIAL = "material"
    LABOUR = "labour"
    EQUIPMENT = "equipment"
    SUBCONTRACT = "subcontract"
    SITE_EXPENSE = "site_expense"
    INDIRECT = "indirect"
    OTHER = "other"


class ProjectCostSourceType(StrEnum):
    WORKFORCE_TIME = "workforce_time"
    MATERIAL_CONSUMPTION = "material_consumption"
    EQUIPMENT_USAGE = "equipment_usage"
    SUBCONTRACT_CLAIM = "subcontract_claim"
    GOODS_RECEIPT = "goods_receipt"
    VENDOR_BILL = "vendor_bill"
    SITE_EXPENSE = "site_expense"
    ADJUSTMENT = "adjustment"


class ProjectCostStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


class SiteCashAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class SiteExpenseStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"
    REVERSED = "reversed"


class SiteCashDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class SiteCashTransactionType(StrEnum):
    ADVANCE = "advance"
    TOP_UP = "top_up"
    EXPENSE = "expense"
    RETURN_TO_COMPANY = "return_to_company"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class CostHead(UUIDTimestampMixin, Base):
    __tablename__ = "cost_heads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_cost_heads_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id", "organization_id"],
            ["cost_heads.id", "cost_heads.organization_id"],
            name="fk_cost_heads_parent_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "code", name="uq_cost_heads_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_cost_heads_id_org"),
        CheckConstraint("revision >= 1", name="ck_cost_heads_revision"),
        Index("ix_cost_heads_org_category_status", "organization_id", "category", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[CostHeadCategory] = mapped_column(
        Enum(CostHeadCategory, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, native_enum=False, values_callable=enum_values),
        default=RecordStatus.ACTIVE,
    )
    allows_posting: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class CostHeadLedgerMapping(UUIDTimestampMixin, Base):
    __tablename__ = "cost_head_ledger_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cost_head_id", "organization_id"],
            ["cost_heads.id", "cost_heads.organization_id"],
            name="fk_cost_head_ledger_mappings_cost_head_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ledger_account_id", "organization_id"],
            ["ledger_accounts.id", "ledger_accounts.organization_id"],
            name="fk_cost_head_ledger_mappings_ledger_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "cost_head_id",
            "effective_from",
            name="uq_cost_head_ledger_mappings_head_start",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_cost_head_ledger_mappings_date_range",
        ),
        CheckConstraint("revision >= 1", name="ck_cost_head_ledger_mappings_revision"),
        Index(
            "ix_cost_head_ledger_mappings_org_head_date",
            "organization_id",
            "cost_head_id",
            "effective_from",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    cost_head_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    ledger_account_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ProjectCostEntry(UUIDTimestampMixin, Base):
    __tablename__ = "project_cost_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_cost_entries_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["posted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_cost_entries_posted_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reversed_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_cost_entries_reversed_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reversal_of_entry_id", "project_id", "organization_id"],
            ["project_cost_entries.id", "project_cost_entries.project_id", "project_cost_entries.organization_id"],
            name="fk_project_cost_entries_reversal_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "entry_number", name="uq_project_cost_entries_project_number"),
        UniqueConstraint(
            "project_id",
            "source_type",
            "source_id",
            name="uq_project_cost_entries_source",
        ),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_project_cost_entries_scope"),
        CheckConstraint("total_amount >= 0", name="ck_project_cost_entries_amount"),
        CheckConstraint("revision >= 1", name="ck_project_cost_entries_revision"),
        Index("ix_project_cost_entries_project_date", "project_id", "entry_date"),
        Index("ix_project_cost_entries_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    entry_number: Mapped[str] = mapped_column(String(80))
    entry_date: Mapped[date] = mapped_column(Date)
    source_type: Mapped[ProjectCostSourceType] = mapped_column(
        Enum(ProjectCostSourceType, native_enum=False, values_callable=enum_values)
    )
    source_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str] = mapped_column(String(500))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[ProjectCostStatus] = mapped_column(
        Enum(ProjectCostStatus, native_enum=False, values_callable=enum_values),
        default=ProjectCostStatus.DRAFT,
    )
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    posted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_of_entry_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectCostAllocation(UUIDTimestampMixin, Base):
    __tablename__ = "project_cost_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cost_entry_id", "project_id", "organization_id"],
            ["project_cost_entries.id", "project_cost_entries.project_id", "project_cost_entries.organization_id"],
            name="fk_project_cost_allocations_entry_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_head_id", "organization_id"],
            ["cost_heads.id", "cost_heads.organization_id"],
            name="fk_project_cost_allocations_cost_head_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_project_cost_allocations_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_project_cost_allocations_boq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_project_cost_allocations_party_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["worker_assignment_id", "project_id", "organization_id"],
            ["project_worker_assignments.id", "project_worker_assignments.project_id", "project_worker_assignments.organization_id"],
            name="fk_project_cost_allocations_worker_assignment_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_asset_id", "organization_id"],
            ["equipment_assets.id", "equipment_assets.organization_id"],
            name="fk_project_cost_allocations_equipment_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_project_cost_allocations_material_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("cost_entry_id", "line_number", name="uq_project_cost_allocations_line"),
        CheckConstraint("amount >= 0", name="ck_project_cost_allocations_amount"),
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="ck_project_cost_allocations_quantity",
        ),
        Index("ix_project_cost_allocations_project_head", "project_id", "cost_head_id"),
        Index("ix_project_cost_allocations_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    cost_entry_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    cost_head_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    party_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    worker_assignment_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    equipment_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))


class SiteCashAccount(UUIDTimestampMixin, Base):
    __tablename__ = "site_cash_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_site_cash_accounts_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["custodian_worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_site_cash_accounts_worker_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["custodian_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_site_cash_accounts_membership_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_site_cash_accounts_project_code"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_site_cash_accounts_scope"),
        CheckConstraint("revision >= 1", name="ck_site_cash_accounts_revision"),
        Index("ix_site_cash_accounts_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    custodian_worker_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    custodian_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[SiteCashAccountStatus] = mapped_column(
        Enum(SiteCashAccountStatus, native_enum=False, values_callable=enum_values),
        default=SiteCashAccountStatus.ACTIVE,
    )
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class SiteExpense(UUIDTimestampMixin, Base):
    __tablename__ = "site_expenses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_site_expenses_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cash_account_id", "project_id", "organization_id"],
            ["site_cash_accounts.id", "site_cash_accounts.project_id", "site_cash_accounts.organization_id"],
            name="fk_site_expenses_cash_account_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["paid_to_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_site_expenses_party_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["submitted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_site_expenses_submitted_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_site_expenses_approved_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["posted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_site_expenses_posted_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "expense_number", name="uq_site_expenses_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_site_expenses_scope"),
        CheckConstraint("gross_amount > 0", name="ck_site_expenses_gross_amount"),
        CheckConstraint("revision >= 1", name="ck_site_expenses_revision"),
        Index("ix_site_expenses_project_status_date", "project_id", "status", "expense_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    expense_number: Mapped[str] = mapped_column(String(80))
    expense_date: Mapped[date] = mapped_column(Date)
    cash_account_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    paid_to_party_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    payment_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[SiteExpenseStatus] = mapped_column(
        Enum(SiteExpenseStatus, native_enum=False, values_callable=enum_values),
        default=SiteExpenseStatus.DRAFT,
    )
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    submitted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SiteExpenseAllocation(UUIDTimestampMixin, Base):
    __tablename__ = "site_expense_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["expense_id", "project_id", "organization_id"],
            ["site_expenses.id", "site_expenses.project_id", "site_expenses.organization_id"],
            name="fk_site_expense_allocations_expense_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["cost_head_id", "organization_id"],
            ["cost_heads.id", "cost_heads.organization_id"],
            name="fk_site_expense_allocations_cost_head_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_site_expense_allocations_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_site_expense_allocations_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("expense_id", "line_number", name="uq_site_expense_allocations_line"),
        CheckConstraint("amount > 0", name="ck_site_expense_allocations_amount"),
        Index("ix_site_expense_allocations_project_head", "project_id", "cost_head_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    expense_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    cost_head_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))


class SiteCashTransaction(UUIDTimestampMixin, Base):
    __tablename__ = "site_cash_transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cash_account_id", "project_id", "organization_id"],
            ["site_cash_accounts.id", "site_cash_accounts.project_id", "site_cash_accounts.organization_id"],
            name="fk_site_cash_transactions_account_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_expense_id", "project_id", "organization_id"],
            ["site_expenses.id", "site_expenses.project_id", "site_expenses.organization_id"],
            name="fk_site_cash_transactions_expense_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["posted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_site_cash_transactions_posted_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "cash_account_id",
            "transaction_number",
            name="uq_site_cash_transactions_account_number",
        ),
        UniqueConstraint(
            "cash_account_id",
            "source_expense_id",
            name="uq_site_cash_transactions_expense",
        ),
        CheckConstraint("amount > 0", name="ck_site_cash_transactions_amount"),
        Index("ix_site_cash_transactions_project_date", "project_id", "transaction_date"),
        Index("ix_site_cash_transactions_account_date", "cash_account_id", "transaction_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    cash_account_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    transaction_number: Mapped[str] = mapped_column(String(80))
    transaction_date: Mapped[date] = mapped_column(Date)
    transaction_type: Mapped[SiteCashTransactionType] = mapped_column(
        Enum(SiteCashTransactionType, native_enum=False, values_callable=enum_values)
    )
    direction: Mapped[SiteCashDirection] = mapped_column(
        Enum(SiteCashDirection, native_enum=False, values_callable=enum_values)
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    source_expense_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posted_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
