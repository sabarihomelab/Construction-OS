from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class DailyReportStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    VOID = "void"


class DailyReportHistoryType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REOPENED = "reopened"
    VOIDED = "voided"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class DailyReport(UUIDTimestampMixin, Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_daily_reports_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "prepared_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_daily_reports_preparer_project_member_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_daily_reports_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_daily_reports_id_org"),
        UniqueConstraint(
            "project_id",
            "report_date",
            "shift_code",
            name="uq_daily_reports_project_date_shift",
        ),
        CheckConstraint("revision >= 1", name="ck_daily_reports_revision"),
        CheckConstraint(
            "temperature_low IS NULL OR temperature_high IS NULL OR temperature_low <= temperature_high",
            name="ck_daily_reports_temperature_range",
        ),
        Index("ix_daily_reports_project_date", "project_id", "report_date"),
        Index("ix_daily_reports_project_status", "project_id", "status", "report_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    shift_code: Mapped[str] = mapped_column(String(40), default="day")
    status: Mapped[DailyReportStatus] = mapped_column(
        Enum(DailyReportStatus, native_enum=False, values_callable=enum_values),
        default=DailyReportStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    prepared_by_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    weather_condition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    temperature_low: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    temperature_high: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    temperature_unit: Mapped[str | None] = mapped_column(String(12), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DailyReportCrewEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_crew_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_crew_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("worker_count >= 0", name="ck_daily_report_crew_worker_count"),
        CheckConstraint("regular_hours >= 0", name="ck_daily_report_crew_regular_hours"),
        CheckConstraint("overtime_hours >= 0", name="ck_daily_report_crew_overtime_hours"),
        Index("ix_daily_report_crew_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    worker_count: Mapped[int] = mapped_column(Integer, default=0)
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportWorkEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_work_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_work_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_daily_report_work_quantity"),
        Index("ix_daily_report_work_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportEquipmentEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_equipment_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_equipment_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("hours_operated >= 0", name="ck_daily_report_equipment_hours"),
        Index("ix_daily_report_equipment_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    equipment_name: Mapped[str] = mapped_column(String(255))
    equipment_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    hours_operated: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportDeliveryEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_delivery_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_delivery_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_daily_report_delivery_quantity"),
        Index("ix_daily_report_delivery_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportProductionEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_production_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_production_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("quantity >= 0", name="ck_daily_report_production_quantity"),
        Index("ix_daily_report_production_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    description: Mapped[str] = mapped_column(String(500))
    cost_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_code: Mapped[str] = mapped_column(String(24))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportDelayEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_delay_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_delay_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("lost_hours IS NULL OR lost_hours >= 0", name="ck_daily_report_delay_hours"),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_daily_report_delay_time_range",
        ),
        Index("ix_daily_report_delay_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    responsible_party: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schedule_impact: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportSafetyEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_safety_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_safety_report_org",
            ondelete="CASCADE",
        ),
        Index("ix_daily_report_safety_report", "daily_report_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    entry_type: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    safety_record_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyReportHistoryEvent(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_history_report_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("report_revision >= 1", name="ck_daily_report_history_revision"),
        Index("ix_daily_report_history_report", "daily_report_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[DailyReportHistoryType] = mapped_column(
        Enum(DailyReportHistoryType, native_enum=False, values_callable=enum_values)
    )
    report_revision: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
