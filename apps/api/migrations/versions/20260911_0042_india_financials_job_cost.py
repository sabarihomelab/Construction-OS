"""Add India financials and job-cost foundation.

Revision ID: 20260911_0042
Revises: 20260911_0041
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0042"
down_revision: str | None = "20260911_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("financials.module.view", "module", "view", "Access project financial and job-cost controls.", "high"),
    ("financials.cost_head.view", "cost_head", "view", "View company construction cost heads and mappings.", "high"),
    ("financials.cost_head.manage", "cost_head", "manage", "Create, revise and retire construction cost heads and ledger mappings.", "critical"),
    ("financials.ledger.view", "ledger", "view", "View company accounting ledger definitions used for integration and governed postings.", "high"),
    ("financials.ledger.manage", "ledger", "manage", "Create, revise and retire company ledger definitions.", "critical"),
    ("financials.project_cost.view", "project_cost", "view", "View project cost entries and allocations.", "high"),
    ("financials.project_cost.post", "project_cost", "post", "Post authoritative project cost entries from approved source records.", "critical"),
    ("financials.project_cost.adjust", "project_cost", "adjust", "Create controlled project cost adjustments and reversals.", "critical"),
    ("financials.site_cash.view", "site_cash", "view", "View project site-cash accounts and transaction history.", "high"),
    ("financials.site_cash.manage", "site_cash", "manage", "Create and manage project site-cash accounts and advances.", "critical"),
    ("financials.site_expense.view", "site_expense", "view", "View site expenses within the authorized project scope.", "high"),
    ("financials.site_expense.create", "site_expense", "create", "Create draft site expenses and cost allocations.", "medium"),
    ("financials.site_expense.approve", "site_expense", "approve", "Approve or reject submitted site expenses.", "high"),
    ("financials.site_expense.post", "site_expense", "post", "Post approved site expenses into site cash and project job cost.", "critical"),
    ("financials.journal.view", "journal", "view", "View governed accounting journal entries.", "high"),
    ("financials.journal.post", "journal", "post", "Post or reverse balanced governed accounting journal entries.", "critical"),
    ("financials.receivable.view", "receivable", "view", "View client invoices, receipts and allocations.", "high"),
    ("financials.receivable.manage", "receivable", "manage", "Create and issue client invoices linked to commercial certification.", "critical"),
    ("financials.receipt.post", "receipt", "post", "Post and allocate client receipts.", "critical"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "financial_project_counters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("next_number >= 1", name="ck_financial_project_counter_next_number"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_financial_project_counters_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "kind", name="pk_financial_project_counters"),
        sa.UniqueConstraint("project_id", "kind", name="uq_financial_project_counter_kind"),
    )
    op.create_index("ix_financial_project_counters_organization_id", "financial_project_counters", ["organization_id"])

    op.create_table(
        "ledger_accounts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.Enum("asset", "liability", "equity", "income", "expense", name="accounttype", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("active", "inactive", name="recordstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("allows_posting", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_ledger_accounts_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_ledger_accounts_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id", "organization_id"], ["ledger_accounts.id", "ledger_accounts.organization_id"], name="fk_ledger_accounts_parent_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_accounts"),
        sa.UniqueConstraint("organization_id", "code", name="uq_ledger_accounts_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_ledger_accounts_id_org"),
    )
    op.create_index("ix_ledger_accounts_organization_id", "ledger_accounts", ["organization_id"])
    op.create_index("ix_ledger_accounts_org_type_status", "ledger_accounts", ["organization_id", "account_type", "status"])

    op.create_table(
        "cost_heads",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.Enum("material", "labour", "equipment", "subcontract", "site_expense", "indirect", "other", name="costheadcategory", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("active", "inactive", name="recordstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("allows_posting", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_cost_heads_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_cost_heads_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id", "organization_id"], ["cost_heads.id", "cost_heads.organization_id"], name="fk_cost_heads_parent_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_cost_heads"),
        sa.UniqueConstraint("organization_id", "code", name="uq_cost_heads_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_cost_heads_id_org"),
    )
    op.create_index("ix_cost_heads_organization_id", "cost_heads", ["organization_id"])
    op.create_index("ix_cost_heads_org_category_status", "cost_heads", ["organization_id", "category", "status"])

    op.create_table(
        "cost_head_ledger_mappings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("cost_head_id", sa.Uuid(), nullable=False),
        sa.Column("ledger_account_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_cost_head_ledger_mappings_date_range"),
        sa.CheckConstraint("revision >= 1", name="ck_cost_head_ledger_mappings_revision"),
        sa.ForeignKeyConstraint(["cost_head_id", "organization_id"], ["cost_heads.id", "cost_heads.organization_id"], name="fk_cost_head_ledger_mappings_cost_head_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_account_id", "organization_id"], ["ledger_accounts.id", "ledger_accounts.organization_id"], name="fk_cost_head_ledger_mappings_ledger_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_cost_head_ledger_mappings"),
        sa.UniqueConstraint("cost_head_id", "effective_from", name="uq_cost_head_ledger_mappings_head_start"),
    )
    op.create_index("ix_cost_head_ledger_mappings_org_head_date", "cost_head_ledger_mappings", ["organization_id", "cost_head_id", "effective_from"])
    op.create_index("ix_cost_head_ledger_mappings_ledger_account_id", "cost_head_ledger_mappings", ["ledger_account_id"])

    op.create_table(
        "journal_entries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("entry_number", sa.String(80), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("source_type", sa.Enum("manual", "purchase_order", "goods_receipt", "subcontract_claim", "workforce", "equipment", "client_invoice", "client_receipt", "adjustment", name="journalsourcetype", native_enum=False), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("status", sa.Enum("draft", "posted", "reversed", name="journalstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_of_entry_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_journal_entries_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_journal_entries_project_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_journal_entries_posted_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_journal_entries_reversed_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_entry_id", "organization_id"], ["journal_entries.id", "journal_entries.organization_id"], name="fk_journal_entries_reversal_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_journal_entries"),
        sa.UniqueConstraint("organization_id", "entry_number", name="uq_journal_entries_org_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_journal_entries_id_org"),
    )
    op.create_index("ix_journal_entries_organization_id", "journal_entries", ["organization_id"])
    op.create_index("ix_journal_entries_project_id", "journal_entries", ["project_id"])
    op.create_index("ix_journal_entries_org_date_status", "journal_entries", ["organization_id", "entry_date", "status"])
    op.create_index("ix_journal_entries_project_date", "journal_entries", ["project_id", "entry_date"])

    op.create_table(
        "journal_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("party_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("debit_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("debit_amount >= 0", name="ck_journal_lines_debit_nonnegative"),
        sa.CheckConstraint("credit_amount >= 0", name="ck_journal_lines_credit_nonnegative"),
        sa.CheckConstraint("(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)", name="ck_journal_lines_one_sided"),
        sa.ForeignKeyConstraint(["journal_entry_id", "organization_id"], ["journal_entries.id", "journal_entries.organization_id"], name="fk_journal_lines_entry_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id", "organization_id"], ["ledger_accounts.id", "ledger_accounts.organization_id"], name="fk_journal_lines_account_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_journal_lines_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_journal_lines_party_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_journal_lines"),
        sa.UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_lines_number"),
    )
    op.create_index("ix_journal_lines_organization_id", "journal_lines", ["organization_id"])
    op.create_index("ix_journal_lines_project_wbs", "journal_lines", ["project_id", "wbs_code_id"])
    op.create_index("ix_journal_lines_account", "journal_lines", ["account_id"])

    op.create_table(
        "project_commitments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.Enum("purchase_order", "subcontract", name="commitmentsourcetype", native_enum=False), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_number", sa.String(80), nullable=False),
        sa.Column("party_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("committed_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.Enum("open", "closed", "cancelled", name="commitmentstatus", native_enum=False), nullable=False, server_default="open"),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("committed_amount >= 0", name="ck_project_commitments_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_project_commitments_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_project_commitments_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_project_commitments_party_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_project_commitments_wbs_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_commitments"),
        sa.UniqueConstraint("project_id", "source_type", "source_id", name="uq_project_commitments_source"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_project_commitments_scope"),
    )
    op.create_index("ix_project_commitments_project_status", "project_commitments", ["project_id", "status"])

    op.create_table(
        "client_invoices",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(80), nullable=False),
        sa.Column("client_party_id", sa.Uuid(), nullable=False),
        sa.Column("source_ra_bill_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("withholding_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("net_receivable", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("draft", "submitted", "approved", "issued", "partially_paid", "paid", "cancelled", name="clientinvoicestatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("subtotal >= 0", name="ck_client_invoices_subtotal"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_client_invoices_tax"),
        sa.CheckConstraint("withholding_amount >= 0", name="ck_client_invoices_withholding"),
        sa.CheckConstraint("total_amount >= 0", name="ck_client_invoices_total"),
        sa.CheckConstraint("net_receivable >= 0", name="ck_client_invoices_net_receivable"),
        sa.CheckConstraint("revision >= 1", name="ck_client_invoices_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_client_invoices_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_client_invoices_party_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_ra_bill_id", "project_id", "organization_id"], ["ra_bills.id", "ra_bills.project_id", "ra_bills.organization_id"], name="fk_client_invoices_ra_bill_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_client_invoices_approved_by_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_client_invoices"),
        sa.UniqueConstraint("project_id", "invoice_number", name="uq_client_invoices_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_client_invoices_scope"),
    )
    op.create_index("ix_client_invoices_project_status", "client_invoices", ["project_id", "status", "invoice_date"])

    op.create_table(
        "client_invoice_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("hsn_sac", sa.String(16), nullable=True),
        sa.Column("tax_code", sa.String(40), nullable=True),
        sa.Column("tax_rate", sa.Numeric(9, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name="ck_client_invoice_lines_quantity"),
        sa.CheckConstraint("rate >= 0", name="ck_client_invoice_lines_rate"),
        sa.CheckConstraint("amount >= 0", name="ck_client_invoice_lines_amount"),
        sa.CheckConstraint("tax_rate >= 0", name="ck_client_invoice_lines_tax_rate"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_client_invoice_lines_tax_amount"),
        sa.ForeignKeyConstraint(["invoice_id", "project_id", "organization_id"], ["client_invoices.id", "client_invoices.project_id", "client_invoices.organization_id"], name="fk_client_invoice_lines_invoice_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_client_invoice_lines_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["boq_item_id", "project_id", "organization_id"], ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"], name="fk_client_invoice_lines_boq_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_client_invoice_lines"),
        sa.UniqueConstraint("invoice_id", "line_number", name="uq_client_invoice_lines_number"),
    )
    op.create_index("ix_client_invoice_lines_project_wbs", "client_invoice_lines", ["project_id", "wbs_code_id"])

    op.create_table(
        "client_receipts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_number", sa.String(80), nullable=False),
        sa.Column("client_party_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payment_method", sa.String(80), nullable=True),
        sa.Column("payment_reference", sa.String(160), nullable=True),
        sa.Column("status", sa.Enum("posted", "reversed", name="clientreceiptstatus", native_enum=False), nullable=False, server_default="posted"),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversal_of_receipt_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_client_receipts_amount"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_client_receipts_project_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_client_receipts_party_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_client_receipts_posted_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_receipt_id", "organization_id"], ["client_receipts.id", "client_receipts.organization_id"], name="fk_client_receipts_reversal_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_client_receipts"),
        sa.UniqueConstraint("project_id", "receipt_number", name="uq_client_receipts_project_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_client_receipts_id_org"),
    )
    op.create_index("ix_client_receipts_project_date", "client_receipts", ["project_id", "receipt_date"])

    op.create_table(
        "client_receipt_allocations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_client_receipt_allocations_amount"),
        sa.ForeignKeyConstraint(["receipt_id", "organization_id"], ["client_receipts.id", "client_receipts.organization_id"], name="fk_client_receipt_allocations_receipt_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id", "project_id", "organization_id"], ["client_invoices.id", "client_invoices.project_id", "client_invoices.organization_id"], name="fk_client_receipt_allocations_invoice_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_client_receipt_allocations"),
        sa.UniqueConstraint("receipt_id", "invoice_id", name="uq_client_receipt_allocation_invoice"),
    )

    op.create_table(
        "project_cost_entries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("entry_number", sa.String(80), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.Enum("workforce_time", "material_consumption", "equipment_usage", "subcontract_claim", "goods_receipt", "vendor_bill", "site_expense", "adjustment", name="projectcostsourcetype", native_enum=False), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.Enum("draft", "posted", "reversed", name="projectcoststatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("configuration_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_of_entry_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("total_amount >= 0", name="ck_project_cost_entries_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_project_cost_entries_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_project_cost_entries_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["posted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_project_cost_entries_posted_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_project_cost_entries_reversed_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_entry_id", "project_id", "organization_id"], ["project_cost_entries.id", "project_cost_entries.project_id", "project_cost_entries.organization_id"], name="fk_project_cost_entries_reversal_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_cost_entries"),
        sa.UniqueConstraint("project_id", "entry_number", name="uq_project_cost_entries_project_number"),
        sa.UniqueConstraint("project_id", "source_type", "source_id", name="uq_project_cost_entries_source"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_project_cost_entries_scope"),
    )
    op.create_index("ix_project_cost_entries_project_date", "project_cost_entries", ["project_id", "entry_date"])
    op.create_index("ix_project_cost_entries_project_status", "project_cost_entries", ["project_id", "status"])

    op.create_table(
        "project_cost_allocations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("cost_entry_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("cost_head_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("party_id", sa.Uuid(), nullable=True),
        sa.Column("worker_assignment_id", sa.Uuid(), nullable=True),
        sa.Column("equipment_asset_id", sa.Uuid(), nullable=True),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("unit_code", sa.String(24), nullable=True),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount >= 0", name="ck_project_cost_allocations_amount"),
        sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_project_cost_allocations_quantity"),
        sa.ForeignKeyConstraint(["cost_entry_id", "project_id", "organization_id"], ["project_cost_entries.id", "project_cost_entries.project_id", "project_cost_entries.organization_id"], name="fk_project_cost_allocations_entry_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_head_id", "organization_id"], ["cost_heads.id", "cost_heads.organization_id"], name="fk_project_cost_allocations_cost_head_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_project_cost_allocations_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["boq_item_id", "project_id", "organization_id"], ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"], name="fk_project_cost_allocations_boq_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_project_cost_allocations_party_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["worker_assignment_id", "project_id", "organization_id"], ["project_worker_assignments.id", "project_worker_assignments.project_id", "project_worker_assignments.organization_id"], name="fk_project_cost_allocations_worker_assignment_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["equipment_asset_id", "organization_id"], ["equipment_assets.id", "equipment_assets.organization_id"], name="fk_project_cost_allocations_equipment_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_id", "organization_id"], ["materials.id", "materials.organization_id"], name="fk_project_cost_allocations_material_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_cost_allocations"),
        sa.UniqueConstraint("cost_entry_id", "line_number", name="uq_project_cost_allocations_line"),
    )
    op.create_index("ix_project_cost_allocations_project_head", "project_cost_allocations", ["project_id", "cost_head_id"])
    op.create_index("ix_project_cost_allocations_project_wbs", "project_cost_allocations", ["project_id", "wbs_code_id"])

    op.create_table(
        "site_cash_accounts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("custodian_worker_id", sa.Uuid(), nullable=True),
        sa.Column("custodian_membership_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("active", "suspended", "closed", name="sitecashaccountstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_site_cash_accounts_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_site_cash_accounts_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["custodian_worker_id", "organization_id"], ["workers.id", "workers.organization_id"], name="fk_site_cash_accounts_worker_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["custodian_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_site_cash_accounts_membership_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_site_cash_accounts"),
        sa.UniqueConstraint("project_id", "code", name="uq_site_cash_accounts_project_code"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_site_cash_accounts_scope"),
    )
    op.create_index("ix_site_cash_accounts_project_status", "site_cash_accounts", ["project_id", "status"])

    op.create_table(
        "site_expenses",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("expense_number", sa.String(80), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("cash_account_id", sa.Uuid(), nullable=True),
        sa.Column("paid_to_party_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payment_method", sa.String(80), nullable=True),
        sa.Column("payment_reference", sa.String(160), nullable=True),
        sa.Column("status", sa.Enum("draft", "submitted", "approved", "posted", "rejected", "reversed", name="siteexpensestatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("configuration_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("submitted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("gross_amount > 0", name="ck_site_expenses_gross_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_site_expenses_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_site_expenses_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cash_account_id", "project_id", "organization_id"], ["site_cash_accounts.id", "site_cash_accounts.project_id", "site_cash_accounts.organization_id"], name="fk_site_expenses_cash_account_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["paid_to_party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_site_expenses_party_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_site_expenses_submitted_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_site_expenses_approved_by_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_site_expenses_posted_by_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_site_expenses"),
        sa.UniqueConstraint("project_id", "expense_number", name="uq_site_expenses_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_site_expenses_scope"),
    )
    op.create_index("ix_site_expenses_project_status_date", "site_expenses", ["project_id", "status", "expense_date"])

    op.create_table(
        "site_expense_allocations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("cost_head_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_site_expense_allocations_amount"),
        sa.ForeignKeyConstraint(["expense_id", "project_id", "organization_id"], ["site_expenses.id", "site_expenses.project_id", "site_expenses.organization_id"], name="fk_site_expense_allocations_expense_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_head_id", "organization_id"], ["cost_heads.id", "cost_heads.organization_id"], name="fk_site_expense_allocations_cost_head_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_site_expense_allocations_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["boq_item_id", "project_id", "organization_id"], ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"], name="fk_site_expense_allocations_boq_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_site_expense_allocations"),
        sa.UniqueConstraint("expense_id", "line_number", name="uq_site_expense_allocations_line"),
    )
    op.create_index("ix_site_expense_allocations_project_head", "site_expense_allocations", ["project_id", "cost_head_id"])

    op.create_table(
        "site_cash_transactions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("cash_account_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_number", sa.String(80), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_type", sa.Enum("advance", "top_up", "expense", "return_to_company", "refund", "adjustment", "reversal", name="sitecashtransactiontype", native_enum=False), nullable=False),
        sa.Column("direction", sa.Enum("inflow", "outflow", name="sitecashdirection", native_enum=False), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("source_expense_id", sa.Uuid(), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_site_cash_transactions_amount"),
        sa.ForeignKeyConstraint(["cash_account_id", "project_id", "organization_id"], ["site_cash_accounts.id", "site_cash_accounts.project_id", "site_cash_accounts.organization_id"], name="fk_site_cash_transactions_account_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_expense_id", "project_id", "organization_id"], ["site_expenses.id", "site_expenses.project_id", "site_expenses.organization_id"], name="fk_site_cash_transactions_expense_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_site_cash_transactions_posted_by_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_site_cash_transactions"),
        sa.UniqueConstraint("cash_account_id", "transaction_number", name="uq_site_cash_transactions_account_number"),
        sa.UniqueConstraint("cash_account_id", "source_expense_id", name="uq_site_cash_transactions_expense"),
    )
    op.create_index("ix_site_cash_transactions_project_date", "site_cash_transactions", ["project_id", "transaction_date"])
    op.create_index("ix_site_cash_transactions_account_date", "site_cash_transactions", ["cash_account_id", "transaction_date"])

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String),
        sa.column("module", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.Text),
        sa.column("risk", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": "financials",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys))
    op.drop_table("site_cash_transactions")
    op.drop_table("site_expense_allocations")
    op.drop_table("site_expenses")
    op.drop_table("site_cash_accounts")
    op.drop_table("project_cost_allocations")
    op.drop_table("project_cost_entries")
    op.drop_table("client_receipt_allocations")
    op.drop_table("client_receipts")
    op.drop_table("client_invoice_lines")
    op.drop_table("client_invoices")
    op.drop_table("project_commitments")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("cost_head_ledger_mappings")
    op.drop_table("cost_heads")
    op.drop_table("ledger_accounts")
    op.drop_table("financial_project_counters")
