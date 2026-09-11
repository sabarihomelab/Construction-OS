from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class EstimateApprovalSnapshot(UUIDTimestampMixin, Base):
    __tablename__ = "estimate_approval_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_approval_snapshots_estimate_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_estimate_approval_snapshots_approved_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "estimate_id", "version_number", name="uq_estimate_approval_snapshot_version"
        ),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_estimate_approval_snapshot_scope"
        ),
        CheckConstraint("version_number >= 1", name="ck_estimate_approval_snapshot_version"),
        CheckConstraint("estimate_revision >= 1", name="ck_estimate_approval_snapshot_revision"),
        Index(
            "ix_estimate_approval_snapshots_project_estimate",
            "project_id",
            "estimate_id",
            "version_number",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    estimate_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    estimate_revision: Mapped[int] = mapped_column(Integer)
    approved_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text)


class EstimateRevisionLink(UUIDTimestampMixin, Base):
    __tablename__ = "estimate_revision_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prior_estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_revision_links_prior_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["revised_estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_revision_links_revised_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_estimate_revision_links_creator_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("revised_estimate_id", name="uq_estimate_revision_links_revised"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_estimate_revision_links_scope"
        ),
        CheckConstraint(
            "prior_estimate_id <> revised_estimate_id", name="ck_estimate_revision_links_distinct"
        ),
        Index("ix_estimate_revision_links_prior", "project_id", "prior_estimate_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    prior_estimate_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    revised_estimate_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    created_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(Text)


class BudgetApprovalSnapshot(UUIDTimestampMixin, Base):
    __tablename__ = "budget_approval_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["budget_id", "project_id", "organization_id"],
            ["project_budgets.id", "project_budgets.project_id", "project_budgets.organization_id"],
            name="fk_budget_approval_snapshots_budget_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["estimate_snapshot_id", "project_id", "organization_id"],
            [
                "estimate_approval_snapshots.id",
                "estimate_approval_snapshots.project_id",
                "estimate_approval_snapshots.organization_id",
            ],
            name="fk_budget_approval_snapshots_estimate_snapshot_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_budget_approval_snapshots_approved_by_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("budget_id", "version_number", name="uq_budget_approval_snapshot_version"),
        UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_budget_approval_snapshot_scope"
        ),
        CheckConstraint("version_number >= 1", name="ck_budget_approval_snapshot_version"),
        CheckConstraint("budget_revision >= 1", name="ck_budget_approval_snapshot_revision"),
        Index(
            "ix_budget_approval_snapshots_project_budget",
            "project_id",
            "budget_id",
            "version_number",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    budget_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    estimate_snapshot_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    budget_revision: Mapped[int] = mapped_column(Integer)
    approved_by_membership_id: Mapped[UUID] = mapped_column(Uuid)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
