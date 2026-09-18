from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
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


class RFQStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class RFQInvitationStatus(StrEnum):
    INVITED = "invited"
    QUOTED = "quoted"
    DECLINED = "declined"


class VendorQuotationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ProcurementSourcingCounter(Base):
    __tablename__ = "procurement_sourcing_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_proc_sourcing_counter_project_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("next_rfq_number >= 1", name="ck_proc_sourcing_counter_rfq"),
        CheckConstraint("next_quote_number >= 1", name="ck_proc_sourcing_counter_quote"),
    )

    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    next_rfq_number: Mapped[int] = mapped_column(BigInteger, default=1)
    next_quote_number: Mapped[int] = mapped_column(BigInteger, default=1)


class RequestForQuotation(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_rfqs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_proc_rfqs_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["requisition_id", "project_id", "organization_id"],
            [
                "purchase_requisitions.id",
                "purchase_requisitions.project_id",
                "purchase_requisitions.organization_id",
            ],
            name="fk_proc_rfqs_requisition_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_proc_rfqs_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfqs_scope"),
        CheckConstraint("revision >= 1", name="ck_proc_rfqs_revision"),
        Index("ix_proc_rfqs_project_status_due", "project_id", "status", "due_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    requisition_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RFQStatus] = mapped_column(
        Enum(RFQStatus, native_enum=False, values_callable=enum_values),
        default=RFQStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RequestForQuotationLine(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_rfq_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_rfq_lines_rfq_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["requisition_line_id", "project_id", "organization_id"],
            [
                "purchase_requisition_lines.id",
                "purchase_requisition_lines.project_id",
                "purchase_requisition_lines.organization_id",
            ],
            name="fk_proc_rfq_lines_requisition_line_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("rfq_id", "line_number", name="uq_proc_rfq_lines_number"),
        UniqueConstraint("rfq_id", "requisition_line_id", name="uq_proc_rfq_lines_req_line"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfq_lines_scope"),
        CheckConstraint("quantity > 0", name="ck_proc_rfq_lines_quantity"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    requisition_line_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RFQVendorInvitation(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_rfq_vendors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_rfq_vendors_rfq_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_proc_rfq_vendors_supplier_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("rfq_id", "supplier_party_id", name="uq_proc_rfq_vendor"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfq_vendors_scope"),
        Index("ix_proc_rfq_vendors_supplier", "organization_id", "supplier_party_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    supplier_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[RFQInvitationStatus] = mapped_column(
        Enum(RFQInvitationStatus, native_enum=False, values_callable=enum_values),
        default=RFQInvitationStatus.INVITED,
    )
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class VendorQuotation(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_vendor_quotations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_vendor_quotes_rfq_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_proc_vendor_quotes_supplier_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_proc_vendor_quotes_project_number"),
        UniqueConstraint("rfq_id", "supplier_party_id", name="uq_proc_vendor_quotes_rfq_supplier"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_vendor_quotes_scope"),
        CheckConstraint("subtotal >= 0", name="ck_proc_vendor_quotes_subtotal"),
        CheckConstraint("tax_total >= 0", name="ck_proc_vendor_quotes_tax_total"),
        CheckConstraint("total >= 0", name="ck_proc_vendor_quotes_total"),
        CheckConstraint("revision >= 1", name="ck_proc_vendor_quotes_revision"),
        Index("ix_proc_vendor_quotes_rfq_status", "rfq_id", "status", "submitted_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    supplier_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[str] = mapped_column(String(64))
    supplier_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quote_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[VendorQuotationStatus] = mapped_column(
        Enum(VendorQuotationStatus, native_enum=False, values_callable=enum_values),
        default=VendorQuotationStatus.DRAFT,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    total: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class VendorQuotationLine(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_vendor_quotation_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["quotation_id", "project_id", "organization_id"],
            [
                "procurement_vendor_quotations.id",
                "procurement_vendor_quotations.project_id",
                "procurement_vendor_quotations.organization_id",
            ],
            name="fk_proc_vendor_quote_lines_quote_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["rfq_line_id", "project_id", "organization_id"],
            ["procurement_rfq_lines.id", "procurement_rfq_lines.project_id", "procurement_rfq_lines.organization_id"],
            name="fk_proc_vendor_quote_lines_rfq_line_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("quotation_id", "line_number", name="uq_proc_vendor_quote_lines_number"),
        UniqueConstraint("quotation_id", "rfq_line_id", name="uq_proc_vendor_quote_lines_rfq_line"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_vendor_quote_lines_scope"),
        CheckConstraint("quantity > 0", name="ck_proc_vendor_quote_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_proc_vendor_quote_lines_unit_price"),
        CheckConstraint("taxable_value >= 0", name="ck_proc_vendor_quote_lines_taxable"),
        CheckConstraint("tax_rate IS NULL OR tax_rate >= 0", name="ck_proc_vendor_quote_lines_tax_rate"),
        CheckConstraint("tax_amount >= 0", name="ck_proc_vendor_quote_lines_tax_amount"),
        CheckConstraint("line_total >= 0", name="ck_proc_vendor_quote_lines_total"),
        CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="ck_proc_vendor_quote_lines_lead"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    quotation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfq_line_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_code: Mapped[str] = mapped_column(String(24))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    hsn_sac: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RFQVendorSelection(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_rfq_vendor_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_rfq_selection_rfq_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["quotation_id", "project_id", "organization_id"],
            [
                "procurement_vendor_quotations.id",
                "procurement_vendor_quotations.project_id",
                "procurement_vendor_quotations.organization_id",
            ],
            name="fk_proc_rfq_selection_quote_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supplier_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_proc_rfq_selection_supplier_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "selected_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_proc_rfq_selection_actor_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_selection_id", "project_id", "organization_id"],
            [
                "procurement_rfq_vendor_selections.id",
                "procurement_rfq_vendor_selections.project_id",
                "procurement_rfq_vendor_selections.organization_id",
            ],
            name="fk_proc_rfq_selection_supersedes_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_rfq_selection_scope"),
        Index("ix_proc_rfq_selection_current", "rfq_id", "superseded_at", "selected_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    quotation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    supplier_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    selected_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comparison_snapshot: Mapped[dict] = mapped_column(JSON)
    supersedes_selection_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseOrderSource(UUIDTimestampMixin, Base):
    __tablename__ = "procurement_purchase_order_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_proc_po_sources_po_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["rfq_id", "project_id", "organization_id"],
            ["procurement_rfqs.id", "procurement_rfqs.project_id", "procurement_rfqs.organization_id"],
            name="fk_proc_po_sources_rfq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["quotation_id", "project_id", "organization_id"],
            [
                "procurement_vendor_quotations.id",
                "procurement_vendor_quotations.project_id",
                "procurement_vendor_quotations.organization_id",
            ],
            name="fk_proc_po_sources_quote_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["selection_id", "project_id", "organization_id"],
            [
                "procurement_rfq_vendor_selections.id",
                "procurement_rfq_vendor_selections.project_id",
                "procurement_rfq_vendor_selections.organization_id",
            ],
            name="fk_proc_po_sources_selection_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("purchase_order_id", name="uq_proc_po_sources_po"),
        UniqueConstraint("selection_id", name="uq_proc_po_sources_selection"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_proc_po_sources_scope"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    quotation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    selection_id: Mapped[UUID] = mapped_column(Uuid, index=True)
