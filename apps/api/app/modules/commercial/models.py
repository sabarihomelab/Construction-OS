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
    ForeignKey,
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


class PartyType(StrEnum):
    CLIENT = "client"
    CONSULTANT = "consultant"
    SUBCONTRACTOR = "subcontractor"
    SUPPLIER = "supplier"
    LABOUR_CONTRACTOR = "labour_contractor"
    OTHER = "other"


class PartyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProjectPartyRole(StrEnum):
    CLIENT = "client"
    PMC = "pmc"
    CONSULTANT = "consultant"
    SUBCONTRACTOR = "subcontractor"
    SUPPLIER = "supplier"
    LABOUR_CONTRACTOR = "labour_contractor"
    OTHER = "other"


class WBSKind(StrEnum):
    GROUP = "group"
    TRADE = "trade"
    WORK_PACKAGE = "work_package"
    COST_CODE = "cost_code"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class BOQStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class MeasurementStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CERTIFIED = "certified"
    REJECTED = "rejected"


class RABillStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CERTIFIED = "certified"
    PAID = "paid"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Party(UUIDTimestampMixin, Base):
    __tablename__ = "commercial_parties"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_commercial_parties_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_commercial_parties_id_org"),
        CheckConstraint("revision >= 1", name="ck_commercial_parties_revision"),
        Index("ix_commercial_parties_org_type_status", "organization_id", "party_type", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    party_type: Mapped[PartyType] = mapped_column(
        Enum(PartyType, native_enum=False, values_callable=enum_values)
    )
    status: Mapped[PartyStatus] = mapped_column(
        Enum(PartyStatus, native_enum=False, values_callable=enum_values),
        default=PartyStatus.ACTIVE,
    )
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ProjectPartyAssignment(UUIDTimestampMixin, Base):
    __tablename__ = "project_party_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_party_assignments_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_project_party_assignments_party_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id", "party_id", "role", name="uq_project_party_assignment_role"
        ),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_project_party_assignment_scope"
        ),
        Index("ix_project_party_assignments_project_role", "project_id", "role"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    role: Mapped[ProjectPartyRole] = mapped_column(
        Enum(ProjectPartyRole, native_enum=False, values_callable=enum_values)
    )
    active: Mapped[bool] = mapped_column(default=True)


class WBSCode(UUIDTimestampMixin, Base):
    __tablename__ = "project_wbs_codes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_wbs_codes_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_project_wbs_codes_parent_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_project_wbs_codes_project_code"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_project_wbs_codes_scope"
        ),
        CheckConstraint("revision >= 1", name="ck_project_wbs_codes_revision"),
        Index("ix_project_wbs_codes_project_parent", "project_id", "parent_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[WBSKind] = mapped_column(
        Enum(WBSKind, native_enum=False, values_callable=enum_values), default=WBSKind.COST_CODE
    )
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, native_enum=False, values_callable=enum_values),
        default=RecordStatus.ACTIVE,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class BOQ(UUIDTimestampMixin, Base):
    __tablename__ = "project_boqs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_boqs_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_boqs_approved_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "code", name="uq_project_boqs_project_code"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_project_boqs_scope"),
        CheckConstraint("revision >= 1", name="ck_project_boqs_revision"),
        Index("ix_project_boqs_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[BOQStatus] = mapped_column(
        Enum(BOQStatus, native_enum=False, values_callable=enum_values), default=BOQStatus.DRAFT
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BOQItem(UUIDTimestampMixin, Base):
    __tablename__ = "project_boq_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boq_id", "project_id", "organization_id"],
            ["project_boqs.id", "project_boqs.project_id", "project_boqs.organization_id"],
            name="fk_project_boq_items_boq_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_project_boq_items_wbs_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("boq_id", "line_number", name="uq_project_boq_items_line_number"),
        UniqueConstraint("boq_id", "item_code", name="uq_project_boq_items_item_code"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_project_boq_items_scope"
        ),
        CheckConstraint("quantity >= 0", name="ck_project_boq_items_quantity"),
        CheckConstraint("rate >= 0", name="ck_project_boq_items_rate"),
        CheckConstraint("amount >= 0", name="ck_project_boq_items_amount"),
        CheckConstraint("revision >= 1", name="ck_project_boq_items_revision"),
        Index("ix_project_boq_items_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    boq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    hsn_sac: Mapped[str | None] = mapped_column(String(16), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class BOQRevision(UUIDTimestampMixin, Base):
    __tablename__ = "project_boq_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boq_id", "project_id", "organization_id"],
            ["project_boqs.id", "project_boqs.project_id", "project_boqs.organization_id"],
            name="fk_project_boq_revisions_boq_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint("boq_id", "version_number", name="uq_project_boq_revision_version"),
        CheckConstraint("version_number >= 1", name="ck_project_boq_revision_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    boq_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    approved_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class MeasurementEntry(UUIDTimestampMixin, Base):
    __tablename__ = "measurement_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_measurement_entries_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_measurement_entries_boq_item_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["recorded_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_measurement_entries_recorded_by_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["certified_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_measurement_entries_certified_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "entry_number", name="uq_measurement_entries_project_number"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_measurement_entries_scope"
        ),
        CheckConstraint("quantity >= 0", name="ck_measurement_entries_quantity"),
        CheckConstraint("revision >= 1", name="ck_measurement_entries_revision"),
        Index("ix_measurement_entries_project_status_date", "project_id", "status", "measurement_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    boq_item_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    entry_number: Mapped[int] = mapped_column(Integer)
    measurement_date: Mapped[date] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    unit_code: Mapped[str] = mapped_column(String(24))
    status: Mapped[MeasurementStatus] = mapped_column(
        Enum(MeasurementStatus, native_enum=False, values_callable=enum_values),
        default=MeasurementStatus.DRAFT,
    )
    recorded_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    certified_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class RABill(UUIDTimestampMixin, Base):
    __tablename__ = "ra_bills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_ra_bills_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["counterparty_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_ra_bills_counterparty_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["certified_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_ra_bills_certified_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "bill_number", name="uq_ra_bills_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_ra_bills_scope"),
        CheckConstraint("revision >= 1", name="ck_ra_bills_revision"),
        CheckConstraint("gross_amount >= 0", name="ck_ra_bills_gross_amount"),
        CheckConstraint("retention_amount >= 0", name="ck_ra_bills_retention_amount"),
        CheckConstraint("statutory_deduction_amount >= 0", name="ck_ra_bills_statutory_deduction_amount"),
        CheckConstraint("other_deduction_amount >= 0", name="ck_ra_bills_other_deduction_amount"),
        Index("ix_ra_bills_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    counterparty_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    bill_number: Mapped[str] = mapped_column(String(80))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[RABillStatus] = mapped_column(
        Enum(RABillStatus, native_enum=False, values_callable=enum_values), default=RABillStatus.DRAFT
    )
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0.00"))
    retention_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0.00"))
    statutory_deduction_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00")
    )
    other_deduction_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00")
    )
    net_payable: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0.00"))
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certified_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RABillLine(UUIDTimestampMixin, Base):
    __tablename__ = "ra_bill_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ra_bill_id", "project_id", "organization_id"],
            ["ra_bills.id", "ra_bills.project_id", "ra_bills.organization_id"],
            name="fk_ra_bill_lines_bill_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_ra_bill_lines_boq_item_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("ra_bill_id", "boq_item_id", name="uq_ra_bill_lines_boq_item"),
        CheckConstraint("current_quantity >= 0", name="ck_ra_bill_lines_current_quantity"),
        CheckConstraint("rate >= 0", name="ck_ra_bill_lines_rate"),
        CheckConstraint("gross_amount >= 0", name="ck_ra_bill_lines_gross_amount"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    ra_bill_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    boq_item_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))


class RABillMeasurement(UUIDTimestampMixin, Base):
    __tablename__ = "ra_bill_measurements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ra_bill_id", "project_id", "organization_id"],
            ["ra_bills.id", "ra_bills.project_id", "ra_bills.organization_id"],
            name="fk_ra_bill_measurements_bill_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["measurement_entry_id", "project_id", "organization_id"],
            ["measurement_entries.id", "measurement_entries.project_id", "measurement_entries.organization_id"],
            name="fk_ra_bill_measurements_entry_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("measurement_entry_id", name="uq_ra_bill_measurements_entry"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    ra_bill_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    measurement_entry_id: Mapped[UUID] = mapped_column(Uuid, index=True)
