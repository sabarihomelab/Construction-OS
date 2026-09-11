from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
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


class RequisitionStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


class PurchaseOrderStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ISSUED = "issued"
    PART_RECEIVED = "part_received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class GoodsReceiptStatus(StrEnum):
    DRAFT = "draft"
    RECEIVED = "received"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ProcurementProjectCounter(Base):
    __tablename__ = "procurement_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_procurement_counter_project_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("next_requisition_number >= 1", name="ck_proc_counter_req"),
        CheckConstraint("next_po_number >= 1", name="ck_proc_counter_po"),
        CheckConstraint("next_grn_number >= 1", name="ck_proc_counter_grn"),
    )

    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    next_requisition_number: Mapped[int] = mapped_column(BigInteger, default=1)
    next_po_number: Mapped[int] = mapped_column(BigInteger, default=1)
    next_grn_number: Mapped[int] = mapped_column(BigInteger, default=1)


class PurchaseRequisition(UUIDTimestampMixin, Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_purchase_requisitions_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "requested_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_purchase_requisitions_requester_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "approved_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_purchase_requisitions_approver_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_purchase_requisitions_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_requisitions_scope"),
        CheckConstraint("revision >= 1", name="ck_purchase_requisitions_revision"),
        Index("ix_purchase_requisitions_project_status", "project_id", "status", "required_by"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    requested_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[RequisitionStatus] = mapped_column(
        Enum(RequisitionStatus, native_enum=False, values_callable=enum_values),
        default=RequisitionStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseRequisitionLine(UUIDTimestampMixin, Base):
    __tablename__ = "purchase_requisition_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requisition_id", "project_id", "organization_id"],
            ["purchase_requisitions.id", "purchase_requisitions.project_id", "purchase_requisitions.organization_id"],
            name="fk_purchase_requisition_lines_req_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_purchase_requisition_lines_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_purchase_requisition_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_purchase_requisition_lines_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("requisition_id", "line_number", name="uq_purchase_requisition_line_number"),
        CheckConstraint("quantity > 0", name="ck_purchase_requisition_lines_quantity"),
        CheckConstraint("estimated_unit_rate >= 0", name="ck_purchase_requisition_lines_rate"),
        CheckConstraint("estimated_amount >= 0", name="ck_purchase_requisition_lines_amount"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    requisition_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    estimated_unit_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseOrder(UUIDTimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_purchase_orders_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_purchase_orders_supplier_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requisition_id", "project_id", "organization_id"],
            ["purchase_requisitions.id", "purchase_requisitions.project_id", "purchase_requisitions.organization_id"],
            name="fk_purchase_orders_requisition_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "approved_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_purchase_orders_approver_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_purchase_orders_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_orders_scope"),
        CheckConstraint("subtotal >= 0", name="ck_purchase_orders_subtotal"),
        CheckConstraint("tax_total >= 0", name="ck_purchase_orders_tax_total"),
        CheckConstraint("total >= 0", name="ck_purchase_orders_total"),
        CheckConstraint("revision >= 1", name="ck_purchase_orders_revision"),
        Index("ix_purchase_orders_project_status", "project_id", "status", "order_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[str] = mapped_column(String(64))
    supplier_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    requisition_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, native_enum=False, values_callable=enum_values),
        default=PurchaseOrderStatus.DRAFT,
    )
    order_date: Mapped[date] = mapped_column(Date)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    total: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseOrderLine(UUIDTimestampMixin, Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_purchase_order_lines_po_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["requisition_line_id", "project_id", "organization_id"],
            ["purchase_requisition_lines.id", "purchase_requisition_lines.project_id", "purchase_requisition_lines.organization_id"],
            name="fk_purchase_order_lines_req_line_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_purchase_order_lines_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_purchase_order_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("purchase_order_id", "line_number", name="uq_purchase_order_line_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_purchase_order_lines_scope"),
        CheckConstraint("quantity > 0", name="ck_purchase_order_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_purchase_order_lines_unit_price"),
        CheckConstraint("taxable_value >= 0", name="ck_purchase_order_lines_taxable"),
        CheckConstraint("tax_rate IS NULL OR tax_rate >= 0", name="ck_purchase_order_lines_tax_rate"),
        CheckConstraint("tax_amount >= 0", name="ck_purchase_order_lines_tax_amount"),
        CheckConstraint("line_total >= 0", name="ck_purchase_order_lines_total"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    requisition_line_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    hsn_sac: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GoodsReceipt(UUIDTimestampMixin, Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_goods_receipts_po_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["stock_location_id", "project_id", "organization_id"],
            [
                "material_stock_locations.id",
                "material_stock_locations.project_id",
                "material_stock_locations.organization_id",
            ],
            name="fk_goods_receipts_stock_location_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "received_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_goods_receipts_receiver_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_goods_receipts_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_goods_receipts_scope"),
        CheckConstraint("revision >= 1", name="ck_goods_receipts_revision"),
        Index("ix_goods_receipts_project_status", "project_id", "status", "received_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    stock_location_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(64))
    status: Mapped[GoodsReceiptStatus] = mapped_column(
        Enum(GoodsReceiptStatus, native_enum=False, values_callable=enum_values),
        default=GoodsReceiptStatus.DRAFT,
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    challan_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class GoodsReceiptLine(UUIDTimestampMixin, Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goods_receipt_id", "project_id", "organization_id"],
            ["goods_receipts.id", "goods_receipts.project_id", "goods_receipts.organization_id"],
            name="fk_goods_receipt_lines_grn_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_order_line_id", "project_id", "organization_id"],
            ["purchase_order_lines.id", "purchase_order_lines.project_id", "purchase_order_lines.organization_id"],
            name="fk_goods_receipt_lines_po_line_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("goods_receipt_id", "purchase_order_line_id", name="uq_goods_receipt_line_po_line"),
        CheckConstraint("received_quantity > 0", name="ck_goods_receipt_lines_received"),
        CheckConstraint("accepted_quantity >= 0", name="ck_goods_receipt_lines_accepted"),
        CheckConstraint("rejected_quantity >= 0", name="ck_goods_receipt_lines_rejected"),
        CheckConstraint(
            "accepted_quantity + rejected_quantity <= received_quantity",
            name="ck_goods_receipt_lines_disposition",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    goods_receipt_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    purchase_order_line_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    accepted_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    rejected_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    unit_code: Mapped[str] = mapped_column(String(24))
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
