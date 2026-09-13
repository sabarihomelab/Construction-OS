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


class ScheduleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ActivityStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class DependencyType(StrEnum):
    FINISH_START = "finish_start"
    START_START = "start_start"
    FINISH_FINISH = "finish_finish"
    START_FINISH = "start_finish"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ProjectSchedule(UUIDTimestampMixin, Base):
    __tablename__ = "project_schedules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_schedules_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", "code", name="uq_project_schedules_project_code"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_project_schedules_scope"),
        CheckConstraint("revision >= 1", name="ck_project_schedules_revision"),
        Index("ix_project_schedules_project_status", "project_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, native_enum=False, values_callable=enum_values),
        default=ScheduleStatus.DRAFT,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    active_baseline_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScheduleActivity(UUIDTimestampMixin, Base):
    __tablename__ = "schedule_activities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["schedule_id", "project_id", "organization_id"],
            ["project_schedules.id", "project_schedules.project_id", "project_schedules.organization_id"],
            name="fk_schedule_activities_schedule_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_schedule_activities_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "responsible_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_schedule_activities_responsible_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("schedule_id", "activity_code", name="uq_schedule_activity_code"),
        UniqueConstraint("id", "schedule_id", "project_id", "organization_id", name="uq_schedule_activity_scope"),
        CheckConstraint("planned_finish >= planned_start", name="ck_schedule_activity_planned_dates"),
        CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_schedule_activity_percent"),
        CheckConstraint("revision >= 1", name="ck_schedule_activity_revision"),
        Index("ix_schedule_activities_project_status", "project_id", "status"),
        Index("ix_schedule_activities_schedule_dates", "schedule_id", "planned_start", "planned_finish"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    schedule_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    activity_code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    responsible_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    planned_start: Mapped[date] = mapped_column(Date)
    planned_finish: Mapped[date] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_finish: Mapped[date | None] = mapped_column(Date, nullable=True)
    percent_complete: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal(0))
    status: Mapped[ActivityStatus] = mapped_column(
        Enum(ActivityStatus, native_enum=False, values_callable=enum_values),
        default=ActivityStatus.NOT_STARTED,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScheduleDependency(UUIDTimestampMixin, Base):
    __tablename__ = "schedule_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["predecessor_activity_id", "schedule_id", "project_id", "organization_id"],
            [
                "schedule_activities.id",
                "schedule_activities.schedule_id",
                "schedule_activities.project_id",
                "schedule_activities.organization_id",
            ],
            name="fk_schedule_dependencies_predecessor_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["successor_activity_id", "schedule_id", "project_id", "organization_id"],
            [
                "schedule_activities.id",
                "schedule_activities.schedule_id",
                "schedule_activities.project_id",
                "schedule_activities.organization_id",
            ],
            name="fk_schedule_dependencies_successor_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "predecessor_activity_id",
            "successor_activity_id",
            "dependency_type",
            name="uq_schedule_dependency_pair",
        ),
        CheckConstraint(
            "predecessor_activity_id <> successor_activity_id",
            name="ck_schedule_dependency_not_self",
        ),
        Index("ix_schedule_dependencies_schedule", "schedule_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    schedule_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    predecessor_activity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    successor_activity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    dependency_type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType, native_enum=False, values_callable=enum_values),
        default=DependencyType.FINISH_START,
    )
    lag_days: Mapped[int] = mapped_column(Integer, default=0)


class ScheduleBaseline(UUIDTimestampMixin, Base):
    __tablename__ = "schedule_baselines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["schedule_id", "project_id", "organization_id"],
            ["project_schedules.id", "project_schedules.project_id", "project_schedules.organization_id"],
            name="fk_schedule_baselines_schedule_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_schedule_baselines_creator_project_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("schedule_id", "version_number", name="uq_schedule_baseline_version"),
        CheckConstraint("version_number >= 1", name="ck_schedule_baseline_version"),
        Index("ix_schedule_baselines_schedule_version", "schedule_id", "version_number"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    schedule_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    created_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON)


class ScheduleProgressUpdate(UUIDTimestampMixin, Base):
    __tablename__ = "schedule_progress_updates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["activity_id", "schedule_id", "project_id", "organization_id"],
            [
                "schedule_activities.id",
                "schedule_activities.schedule_id",
                "schedule_activities.project_id",
                "schedule_activities.organization_id",
            ],
            name="fk_schedule_progress_activity_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "recorded_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_schedule_progress_recorder_project_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_schedule_progress_percent"),
        Index("ix_schedule_progress_activity_date", "activity_id", "data_date"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    schedule_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    activity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    data_date: Mapped[date] = mapped_column(Date)
    percent_complete: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_finish: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
