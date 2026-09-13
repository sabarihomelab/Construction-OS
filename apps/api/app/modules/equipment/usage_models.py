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


class EquipmentRateBasis(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    PER_USAGE = "per_usage"


class EquipmentUsageStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ProjectEquipmentRate(UUIDTimestampMixin, Base):
    __tablename__ = "project_equipment_rates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_equipment_rates_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["equipment_assignment_id", "project_id", "organization_id"],
            [
                "project_equipment_assignments.id",
                "project_equipment_assignments.project_id",
                "project_equipment_assignments.organization_id",
            ],
            name="fk_project_equipment_rates_assignment_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "equipment_assignment_id",
            "effective_from",
            name="uq_project_equipment_rates_assignment_start",
        ),
        UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_project_equipment_rates_scope",
        ),
        CheckConstraint("rate >= 0", name="ck_project_equipment_rates_rate"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_project_equipment_rates_date_range",
        ),
        CheckConstraint("revision >= 1", name="ck_project_equipment_rates_revision"),
        Index(
            "ix_project_equipment_rates_project_assignment_date",
            "project_id",
            "equipment_assignment_id",
            "effective_from",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    equipment_assignment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rate_basis: Mapped[EquipmentRateBasis] = mapped_column(
        Enum(EquipmentRateBasis, native_enum=False, values_callable=enum_values)
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class EquipmentUsage(UUIDTimestampMixin, Base):
    __tablename__ = "equipment_usages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_equipment_usages_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["equipment_assignment_id", "project_id", "organization_id"],
            [
                "project_equipment_assignments.id",
                "project_equipment_assignments.project_id",
                "project_equipment_assignments.organization_id",
            ],
            name="fk_equipment_usages_assignment_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_equipment_usages_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_equipment_usages_boq_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_equipment_usages_creator_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "posted_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_equipment_usages_poster_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "reversed_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_equipment_usages_reverser_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "equipment_assignment_id",
            "usage_date",
            "shift_code",
            name="uq_equipment_usages_assignment_date_shift",
        ),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_equipment_usages_scope"
        ),
        CheckConstraint(
            "operating_hours IS NULL OR operating_hours >= 0",
            name="ck_equipment_usages_operating_hours",
        ),
        CheckConstraint(
            "meter_start IS NULL OR meter_start >= 0",
            name="ck_equipment_usages_meter_start",
        ),
        CheckConstraint(
            "meter_end IS NULL OR meter_end >= 0",
            name="ck_equipment_usages_meter_end",
        ),
        CheckConstraint(
            "(meter_start IS NULL AND meter_end IS NULL) OR "
            "(meter_start IS NOT NULL AND meter_end IS NOT NULL AND meter_end >= meter_start)",
            name="ck_equipment_usages_meter_pair",
        ),
        CheckConstraint(
            "(operating_hours IS NOT NULL AND operating_hours > 0) OR "
            "(meter_start IS NOT NULL AND meter_end IS NOT NULL AND meter_end > meter_start)",
            name="ck_equipment_usages_observed_usage",
        ),
        CheckConstraint("revision >= 1", name="ck_equipment_usages_revision"),
        Index("ix_equipment_usages_project_date", "project_id", "usage_date"),
        Index(
            "ix_equipment_usages_project_assignment",
            "project_id",
            "equipment_assignment_id",
        ),
        Index("ix_equipment_usages_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    equipment_assignment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    usage_date: Mapped[date] = mapped_column(Date)
    shift_code: Mapped[str] = mapped_column(String(40), default="day")
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    operating_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    meter_start: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    meter_end: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EquipmentUsageStatus] = mapped_column(
        Enum(EquipmentUsageStatus, native_enum=False, values_callable=enum_values),
        default=EquipmentUsageStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    created_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    posted_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
