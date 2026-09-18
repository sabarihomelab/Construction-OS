from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class MeetingStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttendanceStatus(StrEnum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    ATTENDED = "attended"
    ABSENT = "absent"


class AgendaItemStatus(StrEnum):
    OPEN = "open"
    DISCUSSED = "discussed"
    DEFERRED = "deferred"
    CLOSED = "closed"


class MeetingActionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MeetingReferenceType(StrEnum):
    RFI = "rfi"
    SUBMITTAL = "submittal"
    DOCUMENT = "document"
    DRAWING = "drawing"
    OTHER = "other"


class MeetingHistoryType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    STARTED = "started"
    MINUTES_UPDATED = "minutes_updated"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"
    ATTENDEE_CHANGED = "attendee_changed"
    AGENDA_CHANGED = "agenda_changed"
    ACTION_CHANGED = "action_changed"
    REFERENCE_CHANGED = "reference_changed"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class MeetingProjectCounter(Base):
    __tablename__ = "meeting_project_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_meeting_counter_project_org",
            ondelete="CASCADE",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    next_number: Mapped[int] = mapped_column(BigInteger, default=1)


class MeetingSeries(UUIDTimestampMixin, Base):
    __tablename__ = "meeting_series"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_meeting_series_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_meeting_series_id_project_org"),
        UniqueConstraint("project_id", "name", name="uq_meeting_series_project_name"),
        CheckConstraint("revision >= 1", name="ck_meeting_series_revision"),
        Index("ix_meeting_series_project_active", "project_id", "active"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recurrence_rule: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class Meeting(UUIDTimestampMixin, Base):
    __tablename__ = "meetings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_meetings_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["series_id", "project_id", "organization_id"],
            ["meeting_series.id", "meeting_series.project_id", "meeting_series.organization_id"],
            name="fk_meetings_series_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "organizer_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_meetings_organizer_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_meetings_workflow_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "number", name="uq_meetings_project_number"),
        UniqueConstraint("id", "project_id", "organization_id", name="uq_meetings_id_project_org"),
        CheckConstraint("number >= 1", name="ck_meetings_number"),
        CheckConstraint("revision >= 1", name="ck_meetings_revision"),
        CheckConstraint("end_at IS NULL OR end_at >= start_at", name="ck_meetings_date_range"),
        Index("ix_meetings_project_status", "project_id", "status", "start_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[int] = mapped_column(BigInteger)
    series_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, native_enum=False, values_callable=enum_values),
        default=MeetingStatus.DRAFT,
    )
    organizer_membership_id: Mapped[UUID] = mapped_column(Uuid)
    minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    configuration_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MeetingAttendee(UUIDTimestampMixin, Base):
    __tablename__ = "meeting_attendees"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id", "project_id", "organization_id"],
            ["meetings.id", "meetings.project_id", "meetings.organization_id"],
            name="fk_meeting_attendee_meeting_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_meeting_attendee_member_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("meeting_id", "membership_id", name="uq_meeting_attendee_internal"),
        CheckConstraint(
            "membership_id IS NOT NULL OR external_name IS NOT NULL",
            name="ck_meeting_attendee_identity",
        ),
        CheckConstraint("revision >= 1", name="ck_meeting_attendee_revision"),
        Index("ix_meeting_attendee_meeting", "meeting_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    meeting_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attendance_status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, values_callable=enum_values),
        default=AttendanceStatus.INVITED,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class MeetingAgendaItem(UUIDTimestampMixin, Base):
    __tablename__ = "meeting_agenda_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id", "project_id", "organization_id"],
            ["meetings.id", "meetings.project_id", "meetings.organization_id"],
            name="fk_meeting_agenda_meeting_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "owner_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_meeting_agenda_owner_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("meeting_id", "sequence", name="uq_meeting_agenda_sequence"),
        CheckConstraint("sequence >= 1", name="ck_meeting_agenda_sequence"),
        CheckConstraint("revision >= 1", name="ck_meeting_agenda_revision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    meeting_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[AgendaItemStatus] = mapped_column(
        Enum(AgendaItemStatus, native_enum=False, values_callable=enum_values),
        default=AgendaItemStatus.OPEN,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class MeetingActionItem(UUIDTimestampMixin, Base):
    __tablename__ = "meeting_action_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id", "project_id", "organization_id"],
            ["meetings.id", "meetings.project_id", "meetings.organization_id"],
            name="fk_meeting_action_meeting_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "assignee_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_meeting_action_assignee_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("meeting_id", "sequence", name="uq_meeting_action_sequence"),
        CheckConstraint("sequence >= 1", name="ck_meeting_action_sequence"),
        CheckConstraint("revision >= 1", name="ck_meeting_action_revision"),
        Index("ix_meeting_action_project_status", "project_id", "status", "due_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    meeting_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    assignee_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[MeetingActionStatus] = mapped_column(
        Enum(MeetingActionStatus, native_enum=False, values_callable=enum_values),
        default=MeetingActionStatus.OPEN,
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MeetingReference(UUIDTimestampMixin, Base):
    __tablename__ = "meeting_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id", "project_id", "organization_id"],
            ["meetings.id", "meetings.project_id", "meetings.organization_id"],
            name="fk_meeting_reference_meeting_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "meeting_id",
            "reference_type",
            "reference_id",
            name="uq_meeting_reference_target",
        ),
        Index("ix_meeting_reference_meeting", "meeting_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    meeting_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    reference_type: Mapped[MeetingReferenceType] = mapped_column(
        Enum(MeetingReferenceType, native_enum=False, values_callable=enum_values)
    )
    reference_id: Mapped[str] = mapped_column(String(160))
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MeetingHistoryEvent(UUIDTimestampMixin, Base):
    __tablename__ = "meeting_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id", "project_id", "organization_id"],
            ["meetings.id", "meetings.project_id", "meetings.organization_id"],
            name="fk_meeting_history_meeting_org",
            ondelete="CASCADE",
        ),
        Index("ix_meeting_history_meeting_created", "meeting_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    meeting_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[MeetingHistoryType] = mapped_column(
        Enum(MeetingHistoryType, native_enum=False, values_callable=enum_values)
    )
    meeting_revision: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
