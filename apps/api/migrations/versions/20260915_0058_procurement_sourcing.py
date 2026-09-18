"""Add India-first procurement sourcing workflow.

Revision ID: 20260915_0058
Revises: 20260912_0057
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0058"
down_revision: str | None = "20260912_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "procurement_sourcing_counters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("next_rfq_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("next_quote_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("next_rfq_number >= 1", name="ck_proc_sourcing_counter_rfq"),
        sa.CheckConstraint("next_quote_number >= 1", name="ck_proc_sourcing_counter_quote"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_proc_sourcing_counter_project_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name="pk_procurement_sourcing_counters"),
    )
    op.create_index(
        "ix_procurement_sourcing_counters_organization_id",
        "procurement_sourcing_counters",
        ["organization_id"],
    )

    op.create_table(
        "procurement_rfqs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "issued", "closed", "cancelled", name="rfqstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_proc_rfqs_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_proc_rfqs_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requisition_id", "project_id", "organization_id"],
            [
                "purchase_requisitions.id",
                "purchase_requisitions.project_id",
                "purchase_requisitions.organization_id",
            ],
            name="fk_proc_rfqs_requisition_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_rfqs"),
        sa.UniqueConstraint("project_id", "number", name="uq_proc_rfqs_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfqs_scope"),
    )
    op.create_index("ix_proc_rfqs_project_status_due", "procurement_rfqs", ["project_id", "status", "due_at"])
    op.create_index("ix_procurement_rfqs_organization_id", "procurement_rfqs", ["organization_id"])
    op.create_index("ix_procurement_rfqs_project_id", "procurement_rfqs", ["project_id"])
    op.create_index("ix_procurement_rfqs_requisition_id", "procurement_rfqs", ["requisition_id"])

    op.create_table(
        "procurement_rfq_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_line_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_proc_rfq_lines_quantity"),
        sa.ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_rfq_lines_rfq_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requisition_line_id", "project_id", "organization_id"],
            [
                "purchase_requisition_lines.id",
                "purchase_requisition_lines.project_id",
                "purchase_requisition_lines.organization_id",
            ],
            name="fk_proc_rfq_lines_requisition_line_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_rfq_lines"),
        sa.UniqueConstraint("rfq_id", "line_number", name="uq_proc_rfq_lines_number"),
        sa.UniqueConstraint("rfq_id", "requisition_line_id", name="uq_proc_rfq_lines_req_line"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfq_lines_scope"),
    )
    for column in ("organization_id", "project_id", "rfq_id", "requisition_line_id", "material_id", "wbs_code_id", "boq_item_id"):
        op.create_index(f"ix_procurement_rfq_lines_{column}", "procurement_rfq_lines", [column])

    op.create_table(
        "procurement_rfq_vendors",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_party_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("invited", "quoted", "declined", name="rfqinvitationstatus", native_enum=False),
            nullable=False,
            server_default="invited",
        ),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_rfq_vendors_rfq_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_proc_rfq_vendors_supplier_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_rfq_vendors"),
        sa.UniqueConstraint("rfq_id", "supplier_party_id", name="uq_proc_rfq_vendor"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfq_vendors_scope"),
    )
    op.create_index(
        "ix_proc_rfq_vendors_supplier",
        "procurement_rfq_vendors",
        ["organization_id", "supplier_party_id", "status"],
    )
    for column in ("organization_id", "project_id", "rfq_id", "supplier_party_id"):
        op.create_index(f"ix_procurement_rfq_vendors_{column}", "procurement_rfq_vendors", [column])

    op.create_table(
        "procurement_vendor_quotations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_party_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("supplier_reference", sa.String(120), nullable=True),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column(
            "status",
            sa.Enum("draft", "submitted", "withdrawn", name="vendorquotationstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("subtotal >= 0", name="ck_proc_vendor_quotes_subtotal"),
        sa.CheckConstraint("tax_total >= 0", name="ck_proc_vendor_quotes_tax_total"),
        sa.CheckConstraint("total >= 0", name="ck_proc_vendor_quotes_total"),
        sa.CheckConstraint("revision >= 1", name="ck_proc_vendor_quotes_revision"),
        sa.ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_vendor_quotes_rfq_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_proc_vendor_quotes_supplier_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_vendor_quotations"),
        sa.UniqueConstraint("project_id", "number", name="uq_proc_vendor_quotes_project_number"),
        sa.UniqueConstraint("rfq_id", "supplier_party_id", name="uq_proc_vendor_quotes_rfq_supplier"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_vendor_quotes_scope"),
    )
    op.create_index("ix_proc_vendor_quotes_rfq_status", "procurement_vendor_quotations", ["rfq_id", "status", "submitted_at"])
    for column in ("organization_id", "project_id", "rfq_id", "supplier_party_id"):
        op.create_index(f"ix_procurement_vendor_quotations_{column}", "procurement_vendor_quotations", [column])

    op.create_table(
        "procurement_vendor_quotation_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("quotation_id", sa.Uuid(), nullable=False),
        sa.Column("rfq_line_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("hsn_sac", sa.String(16), nullable=True),
        sa.Column("tax_code", sa.String(40), nullable=True),
        sa.Column("tax_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(20, 2), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_proc_vendor_quote_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_proc_vendor_quote_lines_unit_price"),
        sa.CheckConstraint("taxable_value >= 0", name="ck_proc_vendor_quote_lines_taxable"),
        sa.CheckConstraint("tax_rate IS NULL OR tax_rate >= 0", name="ck_proc_vendor_quote_lines_tax_rate"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_proc_vendor_quote_lines_tax_amount"),
        sa.CheckConstraint("line_total >= 0", name="ck_proc_vendor_quote_lines_total"),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="ck_proc_vendor_quote_lines_lead"),
        sa.ForeignKeyConstraint(
            ["quotation_id", "project_id", "organization_id"],
            [
                "procurement_vendor_quotations.id",
                "procurement_vendor_quotations.project_id",
                "procurement_vendor_quotations.organization_id",
            ],
            name="fk_proc_vendor_quote_lines_quote_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rfq_line_id", "project_id", "organization_id"],
            ["procurement_rfq_lines.id", "procurement_rfq_lines.project_id", "procurement_rfq_lines.organization_id"],
            name="fk_proc_vendor_quote_lines_rfq_line_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_vendor_quotation_lines"),
        sa.UniqueConstraint("quotation_id", "line_number", name="uq_proc_vendor_quote_lines_number"),
        sa.UniqueConstraint("quotation_id", "rfq_line_id", name="uq_proc_vendor_quote_lines_rfq_line"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_vendor_quote_lines_scope"),
    )
    for column in ("organization_id", "project_id", "quotation_id", "rfq_line_id"):
        op.create_index(f"ix_procurement_vendor_quotation_lines_{column}", "procurement_vendor_quotation_lines", [column])

    op.create_table(
        "procurement_rfq_vendor_selections",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("quotation_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_party_id", sa.Uuid(), nullable=False),
        sa.Column("selected_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comparison_snapshot", sa.JSON(), nullable=False),
        sa.Column("supersedes_selection_id", sa.Uuid(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_rfq_selection_rfq_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id", "project_id", "organization_id"],
            [
                "procurement_vendor_quotations.id",
                "procurement_vendor_quotations.project_id",
                "procurement_vendor_quotations.organization_id",
            ],
            name="fk_proc_rfq_selection_quote_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_proc_rfq_selection_supplier_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "selected_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_proc_rfq_selection_actor_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_selection_id", "project_id", "organization_id"],
            [
                "procurement_rfq_vendor_selections.id",
                "procurement_rfq_vendor_selections.project_id",
                "procurement_rfq_vendor_selections.organization_id",
            ],
            name="fk_proc_rfq_selection_supersedes_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_rfq_vendor_selections"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfq_selection_scope"),
    )
    op.create_index(
        "ix_proc_rfq_selection_current",
        "procurement_rfq_vendor_selections",
        ["rfq_id", "superseded_at", "selected_at"],
    )
    for column in ("organization_id", "project_id", "rfq_id", "quotation_id", "supplier_party_id"):
        op.create_index(f"ix_procurement_rfq_vendor_selections_{column}", "procurement_rfq_vendor_selections", [column])

    op.create_table(
        "procurement_purchase_order_sources",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("quotation_id", sa.Uuid(), nullable=False),
        sa.Column("selection_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_proc_po_sources_po_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_po_sources_rfq_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id", "project_id", "organization_id"],
            [
                "procurement_vendor_quotations.id",
                "procurement_vendor_quotations.project_id",
                "procurement_vendor_quotations.organization_id",
            ],
            name="fk_proc_po_sources_quote_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selection_id", "project_id", "organization_id"],
            [
                "procurement_rfq_vendor_selections.id",
                "procurement_rfq_vendor_selections.project_id",
                "procurement_rfq_vendor_selections.organization_id",
            ],
            name="fk_proc_po_sources_selection_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procurement_purchase_order_sources"),
        sa.UniqueConstraint("purchase_order_id", name="uq_proc_po_sources_po"),
        sa.UniqueConstraint("selection_id", name="uq_proc_po_sources_selection"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_po_sources_scope"),
    )
    for column in ("organization_id", "project_id", "purchase_order_id", "rfq_id", "quotation_id", "selection_id"):
        op.create_index(f"ix_procurement_purchase_order_sources_{column}", "procurement_purchase_order_sources", [column])


def downgrade() -> None:
    op.drop_table("procurement_purchase_order_sources")
    op.drop_table("procurement_rfq_vendor_selections")
    op.drop_table("procurement_vendor_quotation_lines")
    op.drop_table("procurement_vendor_quotations")
    op.drop_table("procurement_rfq_vendors")
    op.drop_table("procurement_rfq_lines")
    op.drop_table("procurement_rfqs")
    op.drop_table("procurement_sourcing_counters")
