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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class VendorBillStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class VendorBillMatchStatus(StrEnum):
    UNCHECKED = "unchecked"
    MATCHED = "matched"
    MISSING_RECEIPT = "missing_receipt"
    QUANTITY_VARIANCE = "quantity_variance"
    PRICE_VARIANCE = "price_variance"
    QUANTITY_AND_PRICE_VARIANCE = "quantity_and_price_variance"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class VendorBill(UUIDTimestampMixin, Base):
    __tablename__ = "vendor_bills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_vendor_bills_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_vendor_bills_supplier_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_vendor_bills_po_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["submitted_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_vendor_bills_submitter_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_vendor_bills_approver_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["variance_override_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_vendor_bills_override_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "bill_number", name="uq_vendor_bills_project_number"),
        UniqueConstraint(
            "organization_id",
            "supplier_party_id",
            "supplier_invoice_number",
            name="uq_vendor_bills_supplier_invoice",
        ),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_vendor_bills_scope"),
        CheckConstraint("subtotal >= 0", name="ck_vendor_bills_subtotal"),
        CheckConstraint("tax_amount >= 0", name="ck_vendor_bills_tax_amount"),
        CheckConstraint("total_amount >= 0", name="ck_vendor_bills_total_amount"),
        CheckConstraint("revision >= 1", name="ck_vendor_bills_revision"),
        Index("ix_vendor_bills_project_status", "project_id", "status", "invoice_date"),
        Index(
            "ix_vendor_bills_supplier_invoice_date",
            "supplier_party_id",
            "invoice_date",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    bill_number: Mapped[str] = mapped_column(String(80))
    supplier_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    supplier_invoice_number: Mapped[str] = mapped_column(String(120))
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    status: Mapped[VendorBillStatus] = mapped_column(
        Enum(VendorBillStatus, native_enum=False, values_callable=enum_values),
        default=VendorBillStatus.DRAFT,
    )
    match_status: Mapped[VendorBillMatchStatus] = mapped_column(
        Enum(VendorBillMatchStatus, native_enum=False, values_callable=enum_values),
        default=VendorBillMatchStatus.UNCHECKED,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    submitted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    variance_override_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    variance_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class VendorBillLine(UUIDTimestampMixin, Base):
    __tablename__ = "vendor_bill_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["vendor_bill_id", "project_id", "organization_id"],
            ["vendor_bills.id", "vendor_bills.project_id", "vendor_bills.organization_id"],
            name="fk_vendor_bill_lines_bill_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_order_line_id", "project_id", "organization_id"],
            ["purchase_order_lines.id", "purchase_order_lines.project_id", "purchase_order_lines.organization_id"],
            name="fk_vendor_bill_lines_po_line_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["goods_receipt_line_id", "project_id", "organization_id"],
            ["goods_receipt_lines.id", "goods_receipt_lines.project_id", "goods_receipt_lines.organization_id"],
            name="fk_vendor_bill_lines_grn_line_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_vendor_bill_lines_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_vendor_bill_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_vendor_bill_lines_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("vendor_bill_id", "line_number", name="uq_vendor_bill_lines_number"),
        CheckConstraint("quantity > 0", name="ck_vendor_bill_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_vendor_bill_lines_unit_price"),
        CheckConstraint("taxable_value >= 0", name="ck_vendor_bill_lines_taxable_value"),
        CheckConstraint("tax_rate IS NULL OR tax_rate >= 0", name="ck_vendor_bill_lines_tax_rate"),
        CheckConstraint("tax_amount >= 0", name="ck_vendor_bill_lines_tax_amount"),
        CheckConstraint("line_total >= 0", name="ck_vendor_bill_lines_line_total"),
        CheckConstraint("matched_quantity >= 0", name="ck_vendor_bill_lines_matched_quantity"),
        CheckConstraint("quantity_variance >= 0", name="ck_vendor_bill_lines_quantity_variance"),
        Index("ix_vendor_bill_lines_project_po", "project_id", "purchase_order_line_id"),
        Index("ix_vendor_bill_lines_project_grn", "project_id", "goods_receipt_line_id"),
        Index("ix_vendor_bill_lines_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    vendor_bill_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(BigInteger)
    purchase_order_line_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    goods_receipt_line_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    unit_code: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    po_unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    hsn_sac: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    matched_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal(0))
    quantity_variance: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal(0))
    price_variance_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    match_status: Mapped[VendorBillMatchStatus] = mapped_column(
        Enum(VendorBillMatchStatus, native_enum=False, values_callable=enum_values),
        default=VendorBillMatchStatus.UNCHECKED,
    )
