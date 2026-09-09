from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Date, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class TimeEntry(UUIDTimestampMixin, Base):
    __tablename__ = "time_entries"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    project_id: Mapped[UUID] = mapped_column(index=True)
    employee_id: Mapped[UUID] = mapped_column(index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    regular_hours: Mapped[float] = mapped_column(Float, default=0)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    cost_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.DRAFT
    )


class DailyLog(UUIDTimestampMixin, Base):
    __tablename__ = "daily_logs"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    project_id: Mapped[UUID] = mapped_column(index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    superintendent_employee_id: Mapped[UUID | None] = mapped_column(nullable=True)
    work_completed: Mapped[str] = mapped_column(Text)
    delays: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.DRAFT
    )
