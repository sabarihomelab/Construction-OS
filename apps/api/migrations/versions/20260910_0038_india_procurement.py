"""Add India procurement foundation.

Revision ID: 20260910_0038
Revises: 20260910_0037
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0038"
down_revision: str | None = "20260910_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("procurement.module.view", "module", "view", "Access procurement workflows.", "medium"),
    ("procurement.requisition.view", "requisition", "view", "View purchase requisitions.", "medium"),
    ("procurement.requisition.create", "requisition", "create", "Create purchase requisitions.", "medium"),
    ("procurement.requisition.manage", "requisition", "manage", "Edit draft requisitions and lines.", "high"),
    ("procurement.requisition.submit", "requisition", "submit", "Submit requisitions for approval.", "high"),
    ("procurement.requisition.approve", "requisition", "approve", "Approve or reject purchase requisitions.", "critical"),
    ("procurement.purchase_order.view", "purchase_order", "view", "View purchase orders.", "high"),
    ("procurement.purchase_order.create", "purchase_order", "create", "Create draft purchase orders.", "high"),
    ("procurement.purchase_order.manage", "purchase_order", "manage", "Edit purchase order lines and terms.", "high"),
    ("procurement.purchase_order.submit", "purchase_order", "submit", "Submit purchase orders for approval.", "high"),
    ("procurement.purchase_order.approve", "purchase_order", "approve", "Approve purchase orders.", "critical"),
    ("procurement.purchase_order.issue", "purchase_order", "issue", "Issue approved purchase orders to suppliers.", "critical"),
    ("procurement.receipt.view", "receipt", "view", "View goods receipts and receipt lines.", "medium"),
    ("procurement.receipt.create", "receipt", "create", "Create goods receipt drafts.", "medium"),
    ("procurement.receipt.manage", "receipt", "manage", "Record goods receipt line quantities and dispositions.", "high"),
    ("procurement.receipt.receive", "receipt", "receive", "Finalize a goods receipt against an issued PO.", "critical"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "procurement_project_counters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("next_requisition_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("next_po_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("next_grn_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("next_requisition_number >= 1", name="ck_proc_counter_req"),
        sa.CheckConstraint("next_po_number >= 1", name="ck_proc_counter_po"),
        sa.CheckConstraint("next_grn_number >= 1", name="ck_proc_counter_grn"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_procurement_counter_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", name="pk_procurement_project_counters"),
    )
    op.create_index("ix_procurement_project_counters_organization_id", "procurement_project_counters", ["organization_id"])

    op.create_table(
        "purchase_requisitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("requested_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("status", sa.Enum("draft", "submitted", "approved", "rejected", "converted", "cancelled", name="requisitionstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_purchase_requisitions_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_purchase_requisitions_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "requested_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_purchase_requisitions_requester_project_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "approved_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_purchase_requisitions_approver_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_requisitions"),
        sa.UniqueConstraint("project_id", "number", name="uq_purchase_requisitions_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_requisitions_scope"),
    )
    op.create_index("ix_purchase_requisitions_project_status", "purchase_requisitions", ["project_id", "status", "required_by"])

    op.create_table(
        "purchase_requisition_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("estimated_unit_rate", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("estimated_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_requisition_lines_quantity"),
        sa.CheckConstraint("estimated_unit_rate >= 0", name="ck_purchase_requisition_lines_rate"),
        sa.CheckConstraint("estimated_amount >= 0", name="ck_purchase_requisition_lines_amount"),
        sa.ForeignKeyConstraint(["requisition_id", "project_id", "organization_id"], ["purchase_requisitions.id", "purchase_requisitions.project_id", "purchase_requisitions.organization_id"], name="fk_purchase_requisition_lines_req_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id", "organization_id"], ["materials.id", "materials.organization_id"], name="fk_purchase_requisition_lines_material_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_purchase_requisition_lines_wbs_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["boq_item_id", "project_id", "organization_id"], ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"], name="fk_purchase_requisition_lines_boq_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_requisition_lines"),
        sa.UniqueConstraint("requisition_id", "line_number", name="uq_purchase_requisition_line_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_requisition_lines_scope"),
    )

    op.create_table(
        "purchase_orders",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("supplier_party_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("draft", "submitted", "approved", "issued", "part_received", "closed", "cancelled", name="purchaseorderstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("subtotal >= 0", name="ck_purchase_orders_subtotal"),
        sa.CheckConstraint("tax_total >= 0", name="ck_purchase_orders_tax_total"),
        sa.CheckConstraint("total >= 0", name="ck_purchase_orders_total"),
        sa.CheckConstraint("revision >= 1", name="ck_purchase_orders_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_purchase_orders_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_party_id", "organization_id"], ["commercial_parties.id", "commercial_parties.organization_id"], name="fk_purchase_orders_supplier_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requisition_id", "project_id", "organization_id"], ["purchase_requisitions.id", "purchase_requisitions.project_id", "purchase_requisitions.organization_id"], name="fk_purchase_orders_requisition_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "approved_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_purchase_orders_approver_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_orders"),
        sa.UniqueConstraint("project_id", "number", name="uq_purchase_orders_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_orders_scope"),
    )
    op.create_index("ix_purchase_orders_project_status", "purchase_orders", ["project_id", "status", "order_date"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_line_id", sa.Uuid(), nullable=True),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("hsn_sac", sa.String(16), nullable=True),
        sa.Column("tax_code", sa.String(40), nullable=True),
        sa.Column("tax_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(20, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_order_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_purchase_order_lines_unit_price"),
        sa.CheckConstraint("taxable_value >= 0", name="ck_purchase_order_lines_taxable"),
        sa.CheckConstraint("tax_rate IS NULL OR tax_rate >= 0", name="ck_purchase_order_lines_tax_rate"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_purchase_order_lines_tax_amount"),
        sa.CheckConstraint("line_total >= 0", name="ck_purchase_order_lines_total"),
        sa.ForeignKeyConstraint(["purchase_order_id", "project_id", "organization_id"], ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"], name="fk_purchase_order_lines_po_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requisition_line_id", "project_id", "organization_id"], ["purchase_requisition_lines.id", "purchase_requisition_lines.project_id", "purchase_requisition_lines.organization_id"], name="fk_purchase_order_lines_req_line_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_id", "organization_id"], ["materials.id", "materials.organization_id"], name="fk_purchase_order_lines_material_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_code_id", "project_id", "organization_id"], ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"], name="fk_purchase_order_lines_wbs_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_order_lines"),
        sa.UniqueConstraint("purchase_order_id", "line_number", name="uq_purchase_order_line_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_order_lines_scope"),
    )

    op.create_table(
        "goods_receipts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("status", sa.Enum("draft", "received", "rejected", "cancelled", name="goodsreceiptstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("challan_number", sa.String(120), nullable=True),
        sa.Column("supplier_invoice_number", sa.String(120), nullable=True),
        sa.Column("delivered_by", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_goods_receipts_revision"),
        sa.ForeignKeyConstraint(["purchase_order_id", "project_id", "organization_id"], ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"], name="fk_goods_receipts_po_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "received_by_membership_id", "organization_id"], ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"], name="fk_goods_receipts_receiver_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_goods_receipts"),
        sa.UniqueConstraint("project_id", "number", name="uq_goods_receipts_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_goods_receipts_scope"),
    )
    op.create_index("ix_goods_receipts_project_status", "goods_receipts", ["project_id", "status", "received_at"])

    op.create_table(
        "goods_receipt_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("goods_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_line_id", sa.Uuid(), nullable=False),
        sa.Column("received_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("accepted_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("rejected_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit_code", sa.String(24), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("received_quantity > 0", name="ck_goods_receipt_lines_received"),
        sa.CheckConstraint("accepted_quantity >= 0", name="ck_goods_receipt_lines_accepted"),
        sa.CheckConstraint("rejected_quantity >= 0", name="ck_goods_receipt_lines_rejected"),
        sa.CheckConstraint("accepted_quantity + rejected_quantity <= received_quantity", name="ck_goods_receipt_lines_disposition"),
        sa.ForeignKeyConstraint(["goods_receipt_id", "project_id", "organization_id"], ["goods_receipts.id", "goods_receipts.project_id", "goods_receipts.organization_id"], name="fk_goods_receipt_lines_grn_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_order_line_id", "project_id", "organization_id"], ["purchase_order_lines.id", "purchase_order_lines.project_id", "purchase_order_lines.organization_id"], name="fk_goods_receipt_lines_po_line_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_goods_receipt_lines"),
        sa.UniqueConstraint("goods_receipt_id", "purchase_order_line_id", name="uq_goods_receipt_line_po_line"),
    )

    permissions = sa.table("permissions", sa.column("key", sa.String), sa.column("module", sa.String), sa.column("resource", sa.String), sa.column("action", sa.String), sa.column("description", sa.Text), sa.column("risk", sa.String), sa.column("is_active", sa.Boolean))
    op.bulk_insert(permissions, [{"key": key, "module": "procurement", "resource": resource, "action": action, "description": description, "risk": risk, "is_active": True} for key, resource, action, description, risk in _PERMISSIONS])


def downgrade() -> None:
    keys = ",".join(f"'{item[0]}'" for item in _PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM permissions WHERE key IN ({keys})"))
    op.drop_table("goods_receipt_lines")
    op.drop_table("goods_receipts")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("purchase_requisition_lines")
    op.drop_table("purchase_requisitions")
    op.drop_table("procurement_project_counters")
