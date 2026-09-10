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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class EmploymentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


class CrewStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class WorkerEngagementType(StrEnum):
    STAFF = "staff"
    DIRECT_LABOUR = "direct_labour"
    CONTRACT_LABOUR = "contract_labour"
    SUBCONTRACTOR_LABOUR = "subcontractor_labour"
    VENDOR_CREW = "vendor_crew"
    OTHER = "other"


class WageBasis(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PIECE_RATE = "piece_rate"
    CONTRACT = "contract"


class ProjectWorkerAssignmentStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


class TimecardStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    VOID = "void"


class TimecardHistoryType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REOPENED = "reopened"
    VOIDED = "voided"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Worker(UUIDTimestampMixin, Base):
    __tablename__ = "workers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_workers_org_membership_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "worker_number", name="uq_workers_org_number"),
        UniqueConstraint("id", "organization_id", name="uq_workers_id_org"),
        UniqueConstraint(
            "organization_id",
            "organization_membership_id",
            name="uq_workers_org_membership",
        ),
        CheckConstraint("revision >= 1", name="ck_workers_revision"),
        Index("ix_workers_org_status", "organization_id", "status"),
        Index("ix_workers_org_name", "organization_id", "last_name", "first_name"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    worker_number: Mapped[str] = mapped_column(String(64), index=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    preferred_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    trade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus, native_enum=False, values_callable=enum_values),
        default=EmploymentStatus.ACTIVE,
    )
    organization_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class Crew(UUIDTimestampMixin, Base):
    __tablename__ = "crews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["supervisor_worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_crews_supervisor_worker_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "name", name="uq_crews_org_name"),
        UniqueConstraint("id", "organization_id", name="uq_crews_id_org"),
        CheckConstraint("revision >= 1", name="ck_crews_revision"),
        Index("ix_crews_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    supervisor_worker_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[CrewStatus] = mapped_column(
        Enum(CrewStatus, native_enum=False, values_callable=enum_values), default=CrewStatus.ACTIVE
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class CrewMembership(UUIDTimestampMixin, Base):
    __tablename__ = "crew_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["crew_id", "organization_id"],
            ["crews.id", "crews.organization_id"],
            name="fk_crew_memberships_crew_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_crew_memberships_worker_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "crew_id",
            "worker_id",
            "effective_from",
            name="uq_crew_memberships_crew_worker_start",
        ),
        CheckConstraint("revision >= 1", name="ck_crew_memberships_revision"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_crew_memberships_date_range",
        ),
        Index("ix_crew_memberships_worker", "organization_id", "worker_id"),
        Index("ix_crew_memberships_crew", "organization_id", "crew_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    crew_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    worker_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ProjectWorkerAssignment(UUIDTimestampMixin, Base):
    __tablename__ = "project_worker_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_worker_assignments_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_project_worker_assignments_worker_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["crew_id", "organization_id"],
            ["crews.id", "crews.organization_id"],
            name="fk_project_worker_assignments_crew_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employer_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_project_worker_assignments_employer_party_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id", "worker_id", name="uq_project_worker_assignments_project_worker"
        ),
        UniqueConstraint(
            "project_id",
            "worker_id",
            "organization_id",
            name="uq_project_worker_assignments_project_worker_org",
        ),
        UniqueConstraint("id", "organization_id", name="uq_project_worker_assignments_id_org"),
        UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_project_worker_assignments_scope",
        ),
        CheckConstraint("revision >= 1", name="ck_project_worker_assignments_revision"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_project_worker_assignments_date_range",
        ),
        Index(
            "ix_project_worker_assignments_project_status",
            "project_id",
            "status",
        ),
        Index(
            "ix_project_worker_assignments_employer",
            "organization_id",
            "employer_party_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    worker_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    crew_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    employer_party_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    engagement_type: Mapped[WorkerEngagementType | None] = mapped_column(
        Enum(WorkerEngagementType, native_enum=False, values_callable=enum_values), nullable=True
    )
    status: Mapped[ProjectWorkerAssignmentStatus] = mapped_column(
        Enum(
            ProjectWorkerAssignmentStatus,
            native_enum=False,
            values_callable=enum_values,
        ),
        default=ProjectWorkerAssignmentStatus.ACTIVE,
    )
    project_role: Mapped[str | None] = mapped_column(String(160), nullable=True)
    trade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_cost_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class ProjectWorkerRate(UUIDTimestampMixin, Base):
    __tablename__ = "project_worker_rates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "project_id", "organization_id"],
            [
                "project_worker_assignments.id",
                "project_worker_assignments.project_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_project_worker_rates_assignment_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "worker_id", "organization_id"],
            [
                "project_worker_assignments.project_id",
                "project_worker_assignments.worker_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_project_worker_rates_worker_assignment_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "assignment_id", "effective_from", name="uq_project_worker_rates_assignment_start"
        ),
        UniqueConstraint("id", "organization_id", name="uq_project_worker_rates_id_org"),
        CheckConstraint("revision >= 1", name="ck_project_worker_rates_revision"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_project_worker_rates_date_range",
        ),
        CheckConstraint("regular_rate >= 0", name="ck_project_worker_rates_regular_nonnegative"),
        CheckConstraint(
            "overtime_rate IS NULL OR overtime_rate >= 0",
            name="ck_project_worker_rates_overtime_nonnegative",
        ),
        CheckConstraint(
            "double_time_rate IS NULL OR double_time_rate >= 0",
            name="ck_project_worker_rates_double_time_nonnegative",
        ),
        CheckConstraint(
            "billing_rate IS NULL OR billing_rate >= 0",
            name="ck_project_worker_rates_billing_nonnegative",
        ),
        Index(
            "ix_project_worker_rates_project_worker_date",
            "project_id",
            "worker_id",
            "effective_from",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    assignment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    worker_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    wage_basis: Mapped[WageBasis] = mapped_column(
        Enum(WageBasis, native_enum=False, values_callable=enum_values)
    )
    regular_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    overtime_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    double_time_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    billing_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class Timecard(UUIDTimestampMixin, Base):
    __tablename__ = "timecards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_timecards_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["worker_id", "organization_id"],
            ["workers.id", "workers.organization_id"],
            name="fk_timecards_worker_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "worker_id", "organization_id"],
            [
                "project_worker_assignments.project_id",
                "project_worker_assignments.worker_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_timecards_project_worker_assignment_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_timecards_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id", "worker_id", "week_start", name="uq_timecards_project_worker_week"
        ),
        UniqueConstraint("id", "organization_id", name="uq_timecards_id_org"),
        CheckConstraint("revision >= 1", name="ck_timecards_revision"),
        Index("ix_timecards_project_week", "project_id", "week_start"),
        Index("ix_timecards_project_status", "project_id", "status", "week_start"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    worker_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[TimecardStatus] = mapped_column(
        Enum(TimecardStatus, native_enum=False, values_callable=enum_values),
        default=TimecardStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TimeEntry(UUIDTimestampMixin, Base):
    __tablename__ = "workforce_time_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["timecard_id", "organization_id"],
            ["timecards.id", "timecards.organization_id"],
            name="fk_workforce_time_entries_timecard_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("regular_hours >= 0", name="ck_workforce_time_entries_regular_hours"),
        CheckConstraint("overtime_hours >= 0", name="ck_workforce_time_entries_overtime_hours"),
        CheckConstraint(
            "double_time_hours >= 0", name="ck_workforce_time_entries_double_time_hours"
        ),
        CheckConstraint(
            "regular_hours + overtime_hours + double_time_hours <= 24",
            name="ck_workforce_time_entries_daily_hours",
        ),
        Index("ix_workforce_time_entries_timecard_date", "timecard_id", "work_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    timecard_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    double_time_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    cost_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class TimecardHistoryEvent(UUIDTimestampMixin, Base):
    __tablename__ = "timecard_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["timecard_id", "organization_id"],
            ["timecards.id", "timecards.organization_id"],
            name="fk_timecard_history_timecard_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("timecard_revision >= 1", name="ck_timecard_history_revision"),
        Index("ix_timecard_history_timecard", "timecard_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    timecard_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[TimecardHistoryType] = mapped_column(
        Enum(TimecardHistoryType, native_enum=False, values_callable=enum_values)
    )
    timecard_revision: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
