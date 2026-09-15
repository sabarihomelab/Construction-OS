"""Add immutable estimating and budget approval history.

Revision ID: 20260911_0049
Revises: 20260911_0048
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0049"
down_revision: str | None = "20260911_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "estimate_approval_snapshots",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("estimate_revision", sa.Integer(), nullable=False),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="ck_estimate_approval_snapshot_version"),
        sa.CheckConstraint("estimate_revision >= 1", name="ck_estimate_approval_snapshot_revision"),
        sa.ForeignKeyConstraint(
            ["estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_approval_snapshots_estimate_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_estimate_approval_snapshots_approved_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "estimate_id", "version_number", name="uq_estimate_approval_snapshot_version"
        ),
        sa.UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_estimate_approval_snapshot_scope"
        ),
    )
    op.create_index(
        "ix_estimate_approval_snapshots_project_estimate",
        "estimate_approval_snapshots",
        ["project_id", "estimate_id", "version_number"],
    )
    op.create_index(
        "ix_estimate_approval_snapshots_estimate_id",
        "estimate_approval_snapshots",
        ["estimate_id"],
    )
    op.create_index(
        "ix_estimate_approval_snapshots_organization_id",
        "estimate_approval_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "ix_estimate_approval_snapshots_project_id",
        "estimate_approval_snapshots",
        ["project_id"],
    )

    op.create_table(
        "estimate_revision_links",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("prior_estimate_id", sa.Uuid(), nullable=False),
        sa.Column("revised_estimate_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "prior_estimate_id <> revised_estimate_id", name="ck_estimate_revision_links_distinct"
        ),
        sa.ForeignKeyConstraint(
            ["prior_estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_revision_links_prior_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revised_estimate_id", "project_id", "organization_id"],
            ["project_estimates.id", "project_estimates.project_id", "project_estimates.organization_id"],
            name="fk_estimate_revision_links_revised_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_estimate_revision_links_creator_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revised_estimate_id", name="uq_estimate_revision_links_revised"),
        sa.UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_estimate_revision_links_scope"
        ),
    )
    op.create_index(
        "ix_estimate_revision_links_prior",
        "estimate_revision_links",
        ["project_id", "prior_estimate_id"],
    )
    op.create_index(
        "ix_estimate_revision_links_prior_estimate_id",
        "estimate_revision_links",
        ["prior_estimate_id"],
    )
    op.create_index(
        "ix_estimate_revision_links_revised_estimate_id",
        "estimate_revision_links",
        ["revised_estimate_id"],
    )
    op.create_index(
        "ix_estimate_revision_links_organization_id",
        "estimate_revision_links",
        ["organization_id"],
    )
    op.create_index(
        "ix_estimate_revision_links_project_id",
        "estimate_revision_links",
        ["project_id"],
    )

    op.create_table(
        "budget_approval_snapshots",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("budget_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("budget_revision", sa.Integer(), nullable=False),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="ck_budget_approval_snapshot_version"),
        sa.CheckConstraint("budget_revision >= 1", name="ck_budget_approval_snapshot_revision"),
        sa.ForeignKeyConstraint(
            ["budget_id", "project_id", "organization_id"],
            ["project_budgets.id", "project_budgets.project_id", "project_budgets.organization_id"],
            name="fk_budget_approval_snapshots_budget_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["estimate_snapshot_id", "project_id", "organization_id"],
            [
                "estimate_approval_snapshots.id",
                "estimate_approval_snapshots.project_id",
                "estimate_approval_snapshots.organization_id",
            ],
            name="fk_budget_approval_snapshots_estimate_snapshot_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_budget_approval_snapshots_approved_by_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_id", "version_number", name="uq_budget_approval_snapshot_version"
        ),
        sa.UniqueConstraint(
            "id", "project_id", "organization_id", name="uq_budget_approval_snapshot_scope"
        ),
    )
    op.create_index(
        "ix_budget_approval_snapshots_project_budget",
        "budget_approval_snapshots",
        ["project_id", "budget_id", "version_number"],
    )
    op.create_index(
        "ix_budget_approval_snapshots_budget_id",
        "budget_approval_snapshots",
        ["budget_id"],
    )
    op.create_index(
        "ix_budget_approval_snapshots_estimate_snapshot_id",
        "budget_approval_snapshots",
        ["estimate_snapshot_id"],
    )
    op.create_index(
        "ix_budget_approval_snapshots_organization_id",
        "budget_approval_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "ix_budget_approval_snapshots_project_id",
        "budget_approval_snapshots",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_table("budget_approval_snapshots")
    op.drop_table("estimate_revision_links")
    op.drop_table("estimate_approval_snapshots")
