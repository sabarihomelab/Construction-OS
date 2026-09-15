"""Add vendor bill and payable reconciliation.

Revision ID: 20260911_0047
Revises: 20260911_0046
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0047"
down_revision: str | None = "20260911_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("financials.payable.view", "payable", "view", "View vendor bills, reconciliation and payable state.", "high"),
    ("financials.payable.create", "payable", "create", "Create vendor bill drafts from issued purchase orders.", "high"),
    ("financials.payable.manage", "payable", "manage", "Edit draft vendor bill lines and receipt allocations.", "high"),
    ("financials.payable.submit", "payable", "submit", "Submit reconciled vendor bills for approval.", "high"),
    ("financials.payable.approve", "payable", "approve", "Approve or reject submitted vendor bills.", "critical"),
    ("financials.payable.override", "payable", "override", "Override vendor bill reconciliation variances with an explicit reason.", "critical"),
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_goods_receipt_lines_scope",
        "goods_receipt_lines",
        ["id", "project_id", "organization_id"],
    )

    op.create_table(
        "vendor_bills",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("bill_number", sa.String(80), nullable=False),
        sa.Column("supplier_party_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_invoice_number", sa.String(120), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("draft", "submitted", "approved", "rejected", "partially_paid", "paid", "cancelled", name="vendorbillstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "match_status",
            sa.Enum("unchecked", "matched", "missing_receipt", "quantity_variance", "price_variance", "quantity_and_price_variance", name="vendorbillmatchstatus", native_enum=False),
            nullable=False,
            server_default="unchecked",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("submitted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("variance_override_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("variance_override_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("subtotal >= 0", name="ck_vendor_bills_subtotal"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_vendor_bills_tax_amount"),
        sa.CheckConstraint("total_amount >= 0", name="ck_vendor_bills_total_amount"),
        sa.CheckConstraint("revision >= 1", name="ck_vendor_bills_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_vendor_bills_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_vendor_bills_supplier_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_order_id", "project_id", "organization_id"], ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"], name="fk_vendor_bills_po_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_vendor_bills_submitter_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_vendor_bills_approver_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variance_override_by_membership_id", "organization_id"], ["organization_memberships.id", "organization_memberships.organization_id"], name="fk_vendor_bills_override_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_vendor_bills"),
        sa.UniqueConstraint("project_id", "bill_number", name="uq_vendor_bills_project_number"),
        sa.UniqueConstraint("organization_id", "supplier_party_id", "supplier_invoice_number", name="uq_vendor_bills_supplier_invoice"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_vendor_bills_scope"),
    )
    op.create_index("ix_vendor_bills_organization_id", "vendor_bills", ["organization_id"])
    op.create_index("ix_vendor_bills_project_id", "vendor_bills", ["project_id"])
    op.create_index("ix_vendor_bills_supplier_party_id", "vendor_bills", ["supplier_party_id"])
    op.create_index("ix_vendor_bills_purchase_order_id", "vendor_bills", ["purchase_order_id"])
    op.create_index("ix_vendor_bills_project_status", "vendor_bills", ["project_id", "status", "invoice_date"])
    op.create_index("ix_vendor_bills_supplier_invoice_date", "vendor_bills", ["supplier_party_id", "invoice_date"])

    op.create_table(
        "vendor_bill_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_bill_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.BigInteger(), nullable=False),
        sa.Column("purchase_order_line_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit_code", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("po_unit_price_snapshot", sa.Numeric(18, 4), nullable=False),
        sa.Column("taxable_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("hsn_sac", sa.String(16), nullable=True),
        sa.Column("tax_code", sa.String(40), nullable=True),
        sa.Column("tax_rate", sa.Numeric(9, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(20, 2), nullable=False),
        sa.Column("matched_quantity", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("quantity_variance", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("price_variance_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column(
            "match_status",
            sa.Enum("unchecked", "matched", "missing_receipt", "quantity_variance", "price_variance", "quantity_and_price_variance", name="vendorbilllinematchstatus", native_enum=False),
            nullable=False,
            server_default="unchecked",
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("quantity > 0", name="ck_vendor_bill_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_vendor_bill_lines_unit_price"),
        sa.CheckConstraint("taxable_value >= 0", name="ck_vendor_bill_lines_taxable_value"),
        sa.CheckConstraint("tax_rate IS NULL OR tax_rate >= 0", name="ck_vendor_bill_lines_tax_rate"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_vendor_bill_lines_tax_amount"),
        sa.CheckConstraint("line_total >= 0", name="ck_vendor_bill_lines_line_total"),
        sa.CheckConstraint("matched_quantity >= 0", name="ck_vendor_bill_lines_matched_quantity"),
        sa.CheckConstraint("quantity_variance >= 0", name="ck_vendor_bill_lines_quantity_variance"),
        sa.ForeignKeyConstraint(["vendor_bill_id", "project_id", "organization_id"], ["vendor_bills.id", "vendor_bills.project_id", "vendor_bills.organization_id"], name="fk_vendor_bill_lines_bill_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_order_line_id", "project_id", "organization_id"], ["purchase_order_lines.id", "purchase_order_lines.project_id", "purchase_order_lines.organization_id"], name="fk_vendor_bill_lines_po_line_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_id", "organization_id"], ["materials.id", "materials.organization_id"], name="fk_vendor_bill_lines_material_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_vendor_bill_lines_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["boq_item_id", "project_id", "organization_id"], ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"], name="fk_vendor_bill_lines_boq_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_vendor_bill_lines"),
        sa.UniqueConstraint("vendor_bill_id", "line_number", name="uq_vendor_bill_lines_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_vendor_bill_lines_scope"),
    )
    op.create_index("ix_vendor_bill_lines_organization_id", "vendor_bill_lines", ["organization_id"])
    op.create_index("ix_vendor_bill_lines_project_id", "vendor_bill_lines", ["project_id"])
    op.create_index("ix_vendor_bill_lines_vendor_bill_id", "vendor_bill_lines", ["vendor_bill_id"])
    op.create_index("ix_vendor_bill_lines_purchase_order_line_id", "vendor_bill_lines", ["purchase_order_line_id"])
    op.create_index("ix_vendor_bill_lines_material_id", "vendor_bill_lines", ["material_id"])
    op.create_index("ix_vendor_bill_lines_wbs_code_id", "vendor_bill_lines", ["wbs_code_id"])
    op.create_index("ix_vendor_bill_lines_boq_item_id", "vendor_bill_lines", ["boq_item_id"])
    op.create_index("ix_vendor_bill_lines_project_po", "vendor_bill_lines", ["project_id", "purchase_order_line_id"])
    op.create_index("ix_vendor_bill_lines_project_wbs", "vendor_bill_lines", ["project_id", "wbs_code_id"])

    op.create_table(
        "vendor_bill_receipt_matches",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_bill_line_id", sa.Uuid(), nullable=False),
        sa.Column("goods_receipt_line_id", sa.Uuid(), nullable=False),
        sa.Column("matched_quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("matched_quantity > 0", name="ck_vendor_bill_receipt_matches_quantity"),
        sa.ForeignKeyConstraint(["vendor_bill_line_id", "project_id", "organization_id"], ["vendor_bill_lines.id", "vendor_bill_lines.project_id", "vendor_bill_lines.organization_id"], name="fk_vendor_bill_receipt_matches_line_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goods_receipt_line_id", "project_id", "organization_id"], ["goods_receipt_lines.id", "goods_receipt_lines.project_id", "goods_receipt_lines.organization_id"], name="fk_vendor_bill_receipt_matches_grn_line_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_vendor_bill_receipt_matches"),
        sa.UniqueConstraint("vendor_bill_line_id", "goods_receipt_line_id", name="uq_vendor_bill_receipt_matches_line_grn"),
    )
    op.create_index("ix_vendor_bill_receipt_matches_organization_id", "vendor_bill_receipt_matches", ["organization_id"])
    op.create_index("ix_vendor_bill_receipt_matches_project_id", "vendor_bill_receipt_matches", ["project_id"])
    op.create_index("ix_vendor_bill_receipt_matches_vendor_bill_line_id", "vendor_bill_receipt_matches", ["vendor_bill_line_id"])
    op.create_index("ix_vendor_bill_receipt_matches_goods_receipt_line_id", "vendor_bill_receipt_matches", ["goods_receipt_line_id"])
    op.create_index("ix_vendor_bill_receipt_matches_grn", "vendor_bill_receipt_matches", ["goods_receipt_line_id"])

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
            {"key": key, "module": "financials", "resource": resource, "action": action, "description": description, "risk": risk, "is_active": True}
            for key, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys))
    op.drop_table("vendor_bill_receipt_matches")
    op.drop_table("vendor_bill_lines")
    op.drop_table("vendor_bills")
    op.drop_constraint("uq_goods_receipt_lines_scope", "goods_receipt_lines", type_="unique")
