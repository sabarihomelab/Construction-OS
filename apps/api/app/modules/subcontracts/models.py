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


class SubcontractStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ISSUED = "issued"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SubcontractClaimStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CERTIFIED = "certified"
    REJECTED = "rejected"
    PAID = "paid"
    CANCELLED = "cancelled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class SubcontractProjectCounter(Base):
    __tablename__ = "subcontract_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_subcontract_counter_project_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("next_contract_number >= 1", name="ck_subcontract_counter_contract"),
        CheckConstraint("next_claim_number >= 1", name="ck_subcontract_counter_claim"),
    )

    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    next_contract_number: Mapped[int] = mapped_column(BigInteger, default=1)
    next_claim_number: Mapped[int] = mapped_column(BigInteger, default=1)


class Subcontract(UUIDTimestampMixin, Base):
    __tablename__ = "subcontracts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_subcontracts_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["contractor_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_subcontracts_contractor_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "approved_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_subcontracts_approver_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_subcontracts_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_subcontracts_scope"),
        CheckConstraint("original_amount >= 0", name="ck_subcontracts_original_amount"),
        CheckConstraint("retention_percent >= 0", name="ck_subcontracts_retention"),
        CheckConstraint("revision >= 1", name="ck_subcontracts_revision"),
        Index("ix_subcontracts_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[str] = mapped_column(String(64))
    contractor_party_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[SubcontractStatus] = mapped_column(
        Enum(SubcontractStatus, native_enum=False, values_callable=enum_values),
        default=SubcontractStatus.DRAFT,
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    retention_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal(0))
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubcontractLine(UUIDTimestampMixin, Base):
    __tablename__ = "subcontract_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subcontract_id", "project_id", "organization_id"],
            ["subcontracts.id", "subcontracts.project_id", "subcontracts.organization_id"],
            name="fk_subcontract_lines_contract_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_subcontract_lines_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_subcontract_lines_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("subcontract_id", "line_number", name="uq_subcontract_line_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_subcontract_lines_scope"),
        CheckConstraint("quantity >= 0", name="ck_subcontract_lines_quantity"),
        CheckConstraint("rate >= 0", name="ck_subcontract_lines_rate"),
        CheckConstraint("amount >= 0", name="ck_subcontract_lines_amount"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    subcontract_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    unit_code: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubcontractClaim(UUIDTimestampMixin, Base):
    __tablename__ = "subcontract_claims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subcontract_id", "project_id", "organization_id"],
            ["subcontracts.id", "subcontracts.project_id", "subcontracts.organization_id"],
            name="fk_subcontract_claims_contract_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "submitted_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_subcontract_claims_submitter_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "certified_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_subcontract_claims_certifier_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_subcontract_claims_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_subcontract_claims_scope"),
        CheckConstraint("gross_amount >= 0", name="ck_subcontract_claims_gross"),
        CheckConstraint("retention_amount >= 0", name="ck_subcontract_claims_retention"),
        CheckConstraint("other_deductions >= 0", name="ck_subcontract_claims_deductions"),
        CheckConstraint("tax_withheld_amount >= 0", name="ck_subcontract_claims_tax_withheld"),
        CheckConstraint("certified_amount >= 0", name="ck_subcontract_claims_certified"),
        CheckConstraint("paid_amount >= 0", name="ck_subcontract_claims_paid"),
        CheckConstraint("revision >= 1", name="ck_subcontract_claims_revision"),
        Index("ix_subcontract_claims_project_status", "project_id", "status", "period_to"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    subcontract_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[str] = mapped_column(String(64))
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    status: Mapped[SubcontractClaimStatus] = mapped_column(
        Enum(SubcontractClaimStatus, native_enum=False, values_callable=enum_values),
        default=SubcontractClaimStatus.DRAFT,
    )
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    retention_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    tax_withheld_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    certified_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    submitted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certified_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubcontractClaimLine(UUIDTimestampMixin, Base):
    __tablename__ = "subcontract_claim_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["claim_id", "project_id", "organization_id"],
            ["subcontract_claims.id", "subcontract_claims.project_id", "subcontract_claims.organization_id"],
            name="fk_subcontract_claim_lines_claim_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["subcontract_line_id", "project_id", "organization_id"],
            ["subcontract_lines.id", "subcontract_lines.project_id", "subcontract_lines.organization_id"],
            name="fk_subcontract_claim_lines_contract_line_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["measurement_entry_id", "project_id", "organization_id"],
            ["measurement_entries.id", "measurement_entries.project_id", "measurement_entries.organization_id"],
            name="fk_subcontract_claim_lines_measurement_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("claim_id", "subcontract_line_id", name="uq_subcontract_claim_line"),
        CheckConstraint("claimed_quantity >= 0", name="ck_subcontract_claim_lines_claimed_qty"),
        CheckConstraint("certified_quantity >= 0", name="ck_subcontract_claim_lines_certified_qty"),
        CheckConstraint("rate >= 0", name="ck_subcontract_claim_lines_rate"),
        CheckConstraint("gross_amount >= 0", name="ck_subcontract_claim_lines_gross"),
        CheckConstraint("certified_amount >= 0", name="ck_subcontract_claim_lines_certified"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    claim_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    subcontract_line_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    measurement_entry_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    claimed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    certified_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal(0))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    certified_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
