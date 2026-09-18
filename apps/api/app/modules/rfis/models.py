from datetime import date, datetime
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
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class RFIStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"
    VOID = "void"


class RFIResponseStatus(StrEnum):
    PROPOSED = "proposed"
    OFFICIAL = "official"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class RFIReferenceType(StrEnum):
    DRAWING_REVISION = "drawing_revision"
    SPECIFICATION_SECTION = "specification_section"
    DOCUMENT_REVISION = "document_revision"
    SCHEDULE_ACTIVITY = "schedule_activity"
    CHANGE_EVENT = "change_event"
    CUSTOM = "custom"


class RFIHistoryType(StrEnum):
    CREATED = "created"
    OPENED = "opened"
    UPDATED = "updated"
    RESPONSE_ADDED = "response_added"
    OFFICIAL_RESPONSE_SET = "official_response_set"
    BALL_IN_COURT_CHANGED = "ball_in_court_changed"
    CLOSED = "closed"
    VOIDED = "voided"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class RFI(UUIDTimestampMixin, Base):
    __tablename__ = "rfis"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_rfis_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "ball_in_court_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_rfis_ball_in_court_project_member_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_rfis_id_org"),
        UniqueConstraint("project_id", "number", name="uq_rfis_project_number"),
        CheckConstraint("version >= 1", name="ck_rfis_version"),
        CheckConstraint("number >= 1", name="ck_rfis_number"),
        Index("ix_rfis_project_status_due", "project_id", "status", "due_date"),
        Index("ix_rfis_project_ball_in_court", "project_id", "ball_in_court_membership_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(500))
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[RFIStatus] = mapped_column(
        Enum(RFIStatus, native_enum=False, values_callable=enum_values),
        default=RFIStatus.DRAFT,
    )
    priority: Mapped[str | None] = mapped_column(String(40), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ball_in_court_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RFIResponse(UUIDTimestampMixin, Base):
    __tablename__ = "rfi_responses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfi_id", "organization_id"],
            ["rfis.id", "rfis.organization_id"],
            name="fk_rfi_responses_rfi_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_rfi_responses_id_org"),
        CheckConstraint("sequence >= 1", name="ck_rfi_responses_sequence"),
        UniqueConstraint("rfi_id", "sequence", name="uq_rfi_responses_rfi_sequence"),
        Index("ix_rfi_responses_rfi_status", "rfi_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfi_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    response_text: Mapped[str] = mapped_column(Text)
    status: Mapped[RFIResponseStatus] = mapped_column(
        Enum(RFIResponseStatus, native_enum=False, values_callable=enum_values),
        default=RFIResponseStatus.PROPOSED,
    )
    responded_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    official_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RFIReference(UUIDTimestampMixin, Base):
    __tablename__ = "rfi_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfi_id", "organization_id"],
            ["rfis.id", "rfis.organization_id"],
            name="fk_rfi_references_rfi_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "rfi_id", "reference_type", "reference_id", name="uq_rfi_references_target"
        ),
        Index("ix_rfi_references_target", "organization_id", "reference_type", "reference_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfi_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    reference_type: Mapped[RFIReferenceType] = mapped_column(
        Enum(RFIReferenceType, native_enum=False, values_callable=enum_values)
    )
    reference_id: Mapped[str] = mapped_column(String(160))
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RFIHistoryEvent(UUIDTimestampMixin, Base):
    __tablename__ = "rfi_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rfi_id", "organization_id"],
            ["rfis.id", "rfis.organization_id"],
            name="fk_rfi_history_rfi_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("entity_version >= 1", name="ck_rfi_history_entity_version"),
        Index("ix_rfi_history_rfi_created", "rfi_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rfi_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[RFIHistoryType] = mapped_column(
        Enum(RFIHistoryType, native_enum=False, values_callable=enum_values)
    )
    entity_version: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str] = mapped_column(String(500))
