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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin
from app.modules.workforce.models import WorkerEngagementType, enum_values


class AttendanceRegisterStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    VOID = "void"


class AttendanceMarkStatus(StrEnum):
    NOT_MARKED = "not_marked"
    PRESENT = "present"
    ABSENT = "absent"
    HALF_DAY = "half_day"
    LEAVE = "leave"
    WEEKLY_OFF = "weekly_off"


class AttendanceHistoryType(StrEnum):
    CREATED = "created"
    POPULATED = "populated"
    UPDATED = "updated"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REOPENED = "reopened"
    VOIDED = "voided"


class AttendanceRegister(UUIDTimestampMixin, Base):
    __tablename__ = "workforce_attendance_registers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_attendance_register_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "prepared_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_attendance_register_preparer_project_member_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "approved_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_attendance_register_approver_project_member_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_attendance_register_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "attendance_date",
            "shift_code",
            name="uq_attendance_register_project_date_shift",
        ),
        UniqueConstraint("id", "organization_id", name="uq_attendance_register_id_org"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_attendance_register_scope"
        ),
        CheckConstraint("revision >= 1", name="ck_attendance_register_revision"),
        Index(
            "ix_attendance_register_project_date",
            "project_id",
            "attendance_date",
            "shift_code",
        ),
        Index(
            "ix_attendance_register_project_status",
            "project_id",
            "status",
            "attendance_date",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    attendance_date: Mapped[date] = mapped_column(Date, index=True)
    shift_code: Mapped[str] = mapped_column(String(40), default="day")
    status: Mapped[AttendanceRegisterStatus] = mapped_column(
        Enum(AttendanceRegisterStatus, native_enum=False, values_callable=enum_values),
        default=AttendanceRegisterStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    prepared_by_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceEntry(UUIDTimestampMixin, Base):
    __tablename__ = "workforce_attendance_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["register_id", "project_id", "organization_id"],
            [
                "workforce_attendance_registers.id",
                "workforce_attendance_registers.project_id",
                "workforce_attendance_registers.organization_id",
            ],
            name="fk_attendance_entry_register_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "project_id", "organization_id"],
            [
                "project_worker_assignments.id",
                "project_worker_assignments.project_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_attendance_entry_assignment_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "worker_id", "organization_id"],
            [
                "project_worker_assignments.project_id",
                "project_worker_assignments.worker_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_attendance_entry_worker_assignment_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["crew_id", "organization_id"],
            ["crews.id", "crews.organization_id"],
            name="fk_attendance_entry_crew_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employer_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_attendance_entry_employer_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_attendance_entry_wbs_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("register_id", "worker_id", name="uq_attendance_entry_register_worker"),
        UniqueConstraint("id", "organization_id", name="uq_attendance_entry_id_org"),
        CheckConstraint("regular_hours >= 0", name="ck_attendance_entry_regular_hours"),
        CheckConstraint("overtime_hours >= 0", name="ck_attendance_entry_overtime_hours"),
        CheckConstraint(
            "regular_hours + overtime_hours <= 24",
            name="ck_attendance_entry_total_hours",
        ),
        Index("ix_attendance_entry_register_status", "register_id", "mark_status"),
        Index("ix_attendance_entry_worker_date", "worker_id", "register_id"),
        Index("ix_attendance_entry_wbs", "project_id", "wbs_code_id"),
        Index("ix_attendance_entry_employer", "project_id", "employer_party_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    register_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    assignment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    worker_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    crew_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    employer_party_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    engagement_type: Mapped[WorkerEngagementType | None] = mapped_column(
        Enum(WorkerEngagementType, native_enum=False, values_callable=enum_values),
        nullable=True,
    )
    trade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mark_status: Mapped[AttendanceMarkStatus] = mapped_column(
        Enum(AttendanceMarkStatus, native_enum=False, values_callable=enum_values),
        default=AttendanceMarkStatus.NOT_MARKED,
    )
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal(0))
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal(0))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    context_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class AttendanceHistoryEvent(UUIDTimestampMixin, Base):
    __tablename__ = "workforce_attendance_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["register_id", "organization_id"],
            ["workforce_attendance_registers.id", "workforce_attendance_registers.organization_id"],
            name="fk_attendance_history_register_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("register_revision >= 1", name="ck_attendance_history_revision"),
        Index("ix_attendance_history_register", "register_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    register_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[AttendanceHistoryType] = mapped_column(
        Enum(AttendanceHistoryType, native_enum=False, values_callable=enum_values)
    )
    register_revision: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
