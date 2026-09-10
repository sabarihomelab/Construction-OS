from datetime import date, datetime
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
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class SubmittalStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    APPROVED_AS_NOTED = "approved_as_noted"
    REVISE_RESUBMIT = "revise_resubmit"
    REJECTED = "rejected"
    CLOSED = "closed"
    VOID = "void"


class SubmittalRevisionStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class SubmittalReviewDecision(StrEnum):
    APPROVED = "approved"
    APPROVED_AS_NOTED = "approved_as_noted"
    REVISE_RESUBMIT = "revise_resubmit"
    REJECTED = "rejected"
    COMMENT_ONLY = "comment_only"


class SubmittalReferenceType(StrEnum):
    SPECIFICATION_SECTION = "specification_section"
    DRAWING_REVISION = "drawing_revision"
    DOCUMENT_REVISION = "document_revision"
    RFI = "rfi"
    SCHEDULE_ACTIVITY = "schedule_activity"
    CUSTOM = "custom"


class SubmittalHistoryType(StrEnum):
    CREATED = "created"
    OPENED = "opened"
    UPDATED = "updated"
    REVISION_CREATED = "revision_created"
    REVISION_SUBMITTED = "revision_submitted"
    REVIEW_ADDED = "review_added"
    DECISION_ISSUED = "decision_issued"
    BALL_IN_COURT_CHANGED = "ball_in_court_changed"
    CLOSED = "closed"
    VOIDED = "voided"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Submittal(UUIDTimestampMixin, Base):
    __tablename__ = "submittals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_submittals_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "ball_in_court_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_submittals_ball_in_court_project_member_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_submittals_id_org"),
        UniqueConstraint("project_id", "number", name="uq_submittals_project_number"),
        CheckConstraint("number >= 1", name="ck_submittals_number"),
        CheckConstraint("version >= 1", name="ck_submittals_version"),
        CheckConstraint(
            "current_revision_sequence >= 0",
            name="ck_submittals_current_revision_sequence",
        ),
        CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="ck_submittals_lead_time_days",
        ),
        Index("ix_submittals_project_status_due", "project_id", "status", "due_date"),
        Index(
            "ix_submittals_project_ball_in_court",
            "project_id",
            "ball_in_court_membership_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    submittal_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[SubmittalStatus] = mapped_column(
        Enum(SubmittalStatus, native_enum=False, values_callable=enum_values),
        default=SubmittalStatus.DRAFT,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_on_site_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ball_in_court_membership_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    latest_decision: Mapped[SubmittalReviewDecision | None] = mapped_column(
        Enum(SubmittalReviewDecision, native_enum=False, values_callable=enum_values),
        nullable=True,
    )
    current_revision_sequence: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SubmittalRevision(UUIDTimestampMixin, Base):
    __tablename__ = "submittal_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["submittal_id", "organization_id"],
            ["submittals.id", "submittals.organization_id"],
            name="fk_submittal_revisions_submittal_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_submittal_revisions_id_org"),
        UniqueConstraint(
            "submittal_id", "sequence", name="uq_submittal_revisions_submittal_sequence"
        ),
        UniqueConstraint(
            "submittal_id",
            "revision_label",
            name="uq_submittal_revisions_submittal_label",
        ),
        CheckConstraint("sequence >= 1", name="ck_submittal_revisions_sequence"),
        Index("ix_submittal_revisions_parent_status", "submittal_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submittal_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    revision_label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SubmittalRevisionStatus] = mapped_column(
        Enum(SubmittalRevisionStatus, native_enum=False, values_callable=enum_values),
        default=SubmittalRevisionStatus.DRAFT,
    )
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubmittalReview(UUIDTimestampMixin, Base):
    __tablename__ = "submittal_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["submittal_revision_id", "organization_id"],
            ["submittal_revisions.id", "submittal_revisions.organization_id"],
            name="fk_submittal_reviews_revision_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["reviewer_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_submittal_reviews_reviewer_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_submittal_reviews_id_org"),
        UniqueConstraint(
            "submittal_revision_id", "sequence", name="uq_submittal_reviews_revision_sequence"
        ),
        CheckConstraint("sequence >= 1", name="ck_submittal_reviews_sequence"),
        Index("ix_submittal_reviews_revision_decision", "submittal_revision_id", "decision"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submittal_revision_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    reviewer_membership_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    decision: Mapped[SubmittalReviewDecision] = mapped_column(
        Enum(SubmittalReviewDecision, native_enum=False, values_callable=enum_values)
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    official: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SubmittalReference(UUIDTimestampMixin, Base):
    __tablename__ = "submittal_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["submittal_id", "organization_id"],
            ["submittals.id", "submittals.organization_id"],
            name="fk_submittal_references_submittal_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "submittal_id",
            "reference_type",
            "reference_id",
            name="uq_submittal_references_target",
        ),
        Index(
            "ix_submittal_references_target",
            "organization_id",
            "reference_type",
            "reference_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submittal_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    reference_type: Mapped[SubmittalReferenceType] = mapped_column(
        Enum(SubmittalReferenceType, native_enum=False, values_callable=enum_values)
    )
    reference_id: Mapped[str] = mapped_column(String(160))
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SubmittalHistoryEvent(UUIDTimestampMixin, Base):
    __tablename__ = "submittal_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["submittal_id", "organization_id"],
            ["submittals.id", "submittals.organization_id"],
            name="fk_submittal_history_submittal_org",
            ondelete="CASCADE",
        ),
        CheckConstraint("entity_version >= 1", name="ck_submittal_history_entity_version"),
        Index("ix_submittal_history_parent_created", "submittal_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submittal_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[SubmittalHistoryType] = mapped_column(
        Enum(SubmittalHistoryType, native_enum=False, values_callable=enum_values)
    )
    entity_version: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str] = mapped_column(String(500))
