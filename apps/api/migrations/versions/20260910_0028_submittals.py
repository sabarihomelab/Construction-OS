"""Add project-scoped Submittal management.

Revision ID: 20260910_0028
Revises: 20260910_0027
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0028"
down_revision: str | None = "20260910_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBMITTAL_PERMISSIONS = (
    (
        "submittals.submittal.view",
        "submittals",
        "submittal",
        "view",
        "View Submittals, revisions, reviews, references and history in the authorized project scope.",
        "medium",
    ),
    (
        "submittals.submittal.create",
        "submittals",
        "submittal",
        "create",
        "Create draft Submittals in the authorized project scope.",
        "medium",
    ),
    (
        "submittals.submittal.update",
        "submittals",
        "submittal",
        "update",
        "Edit Submittals, create revisions and manage controlled references.",
        "medium",
    ),
    (
        "submittals.submittal.submit",
        "submittals",
        "submittal",
        "submit",
        "Submit a Submittal revision for review and assign the reviewer.",
        "high",
    ),
    (
        "submittals.submittal.review",
        "submittals",
        "submittal",
        "review",
        "Add review comments and issue official Submittal decisions.",
        "high",
    ),
    (
        "submittals.submittal.close",
        "submittals",
        "submittal",
        "close",
        "Close approved Submittals in the authorized project scope.",
        "high",
    ),
    (
        "submittals.submittal.manage",
        "submittals",
        "submittal",
        "manage",
        "Manage Submittal responsibility and controlled void actions.",
        "high",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "submittal_project_counters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "next_number >= 1",
            name="ck_submittal_project_counters_next_number",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_submittal_project_counters_project_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name="pk_submittal_project_counters"),
        sa.UniqueConstraint(
            "project_id",
            name="uq_submittal_project_counters_project",
        ),
    )
    op.create_index(
        "ix_submittal_project_counters_organization_id",
        "submittal_project_counters",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "submittals",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("submittal_type", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "open",
                "in_review",
                "approved",
                "approved_as_noted",
                "revise_resubmit",
                "rejected",
                "closed",
                "void",
                name="submittalstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("required_on_site_date", sa.Date(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("ball_in_court_membership_id", sa.Uuid(), nullable=True),
        sa.Column(
            "latest_decision",
            sa.Enum(
                "approved",
                "approved_as_noted",
                "revise_resubmit",
                "rejected",
                "comment_only",
                name="submittalreviewdecision",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("current_revision_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("number >= 1", name="ck_submittals_number"),
        sa.CheckConstraint("version >= 1", name="ck_submittals_version"),
        sa.CheckConstraint(
            "current_revision_sequence >= 0",
            name="ck_submittals_current_revision_sequence",
        ),
        sa.CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="ck_submittals_lead_time_days",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_submittals_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "ball_in_court_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_submittals_ball_in_court_project_member_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_submittals_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submittals"),
        sa.UniqueConstraint("id", "organization_id", name="uq_submittals_id_org"),
        sa.UniqueConstraint("project_id", "number", name="uq_submittals_project_number"),
    )
    op.create_index("ix_submittals_organization_id", "submittals", ["organization_id"])
    op.create_index("ix_submittals_project_id", "submittals", ["project_id"])
    op.create_index(
        "ix_submittals_project_status_due",
        "submittals",
        ["project_id", "status", "due_date"],
    )
    op.create_index(
        "ix_submittals_project_ball_in_court",
        "submittals",
        ["project_id", "ball_in_court_membership_id"],
    )

    op.create_table(
        "submittal_revisions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("submittal_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("revision_label", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "in_review",
                "reviewed",
                "superseded",
                "withdrawn",
                name="submittalrevisionstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_submittal_revisions_sequence"),
        sa.ForeignKeyConstraint(
            ["submittal_id", "organization_id"],
            ["submittals.id", "submittals.organization_id"],
            name="fk_submittal_revisions_submittal_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name="fk_submittal_revisions_submitted_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submittal_revisions"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_submittal_revisions_id_org"
        ),
        sa.UniqueConstraint(
            "submittal_id",
            "sequence",
            name="uq_submittal_revisions_submittal_sequence",
        ),
        sa.UniqueConstraint(
            "submittal_id",
            "revision_label",
            name="uq_submittal_revisions_submittal_label",
        ),
    )
    op.create_index(
        "ix_submittal_revisions_organization_id",
        "submittal_revisions",
        ["organization_id"],
    )
    op.create_index(
        "ix_submittal_revisions_submittal_id",
        "submittal_revisions",
        ["submittal_id"],
    )
    op.create_index(
        "ix_submittal_revisions_parent_status",
        "submittal_revisions",
        ["submittal_id", "status"],
    )

    op.create_table(
        "submittal_reviews",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("submittal_revision_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("reviewer_membership_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "approved",
                "approved_as_noted",
                "revise_resubmit",
                "rejected",
                "comment_only",
                name="submittalreviewdecision",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("official", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_submittal_reviews_sequence"),
        sa.ForeignKeyConstraint(
            ["submittal_revision_id", "organization_id"],
            ["submittal_revisions.id", "submittal_revisions.organization_id"],
            name="fk_submittal_reviews_revision_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "reviewer_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_submittal_reviews_project_reviewer_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name="fk_submittal_reviews_reviewed_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submittal_reviews"),
        sa.UniqueConstraint("id", "organization_id", name="uq_submittal_reviews_id_org"),
        sa.UniqueConstraint(
            "submittal_revision_id",
            "sequence",
            name="uq_submittal_reviews_revision_sequence",
        ),
    )
    op.create_index(
        "ix_submittal_reviews_organization_id",
        "submittal_reviews",
        ["organization_id"],
    )
    op.create_index(
        "ix_submittal_reviews_project_id",
        "submittal_reviews",
        ["project_id"],
    )
    op.create_index(
        "ix_submittal_reviews_submittal_revision_id",
        "submittal_reviews",
        ["submittal_revision_id"],
    )
    op.create_index(
        "ix_submittal_reviews_reviewer_membership_id",
        "submittal_reviews",
        ["reviewer_membership_id"],
    )
    op.create_index(
        "ix_submittal_reviews_revision_decision",
        "submittal_reviews",
        ["submittal_revision_id", "decision"],
    )
    op.create_index(
        "uq_submittal_reviews_one_official",
        "submittal_reviews",
        ["submittal_revision_id"],
        unique=True,
        postgresql_where=sa.text("official"),
    )

    op.create_table(
        "submittal_references",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("submittal_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reference_type",
            sa.Enum(
                "specification_section",
                "drawing_revision",
                "document_revision",
                "rfi",
                "schedule_activity",
                "custom",
                name="submittalreferencetype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reference_id", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["submittal_id", "organization_id"],
            ["submittals.id", "submittals.organization_id"],
            name="fk_submittal_references_submittal_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submittal_references"),
        sa.UniqueConstraint(
            "submittal_id",
            "reference_type",
            "reference_id",
            name="uq_submittal_references_target",
        ),
    )
    op.create_index(
        "ix_submittal_references_organization_id",
        "submittal_references",
        ["organization_id"],
    )
    op.create_index(
        "ix_submittal_references_submittal_id",
        "submittal_references",
        ["submittal_id"],
    )
    op.create_index(
        "ix_submittal_references_target",
        "submittal_references",
        ["organization_id", "reference_type", "reference_id"],
    )

    op.create_table(
        "submittal_history_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("submittal_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "created",
                "opened",
                "updated",
                "revision_created",
                "revision_submitted",
                "review_added",
                "decision_issued",
                "ball_in_court_changed",
                "closed",
                "voided",
                name="submittalhistorytype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_version", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "entity_version >= 1",
            name="ck_submittal_history_entity_version",
        ),
        sa.ForeignKeyConstraint(
            ["submittal_id", "organization_id"],
            ["submittals.id", "submittals.organization_id"],
            name="fk_submittal_history_submittal_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_submittal_history_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submittal_history_events"),
    )
    op.create_index(
        "ix_submittal_history_events_organization_id",
        "submittal_history_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_submittal_history_events_submittal_id",
        "submittal_history_events",
        ["submittal_id"],
    )
    op.create_index(
        "ix_submittal_history_parent_created",
        "submittal_history_events",
        ["submittal_id", "created_at"],
    )

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("risk", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": module,
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, module, resource, action, description, risk in _SUBMITTAL_PERMISSIONS
        ],
    )


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in _SUBMITTAL_PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")
    op.drop_table("submittal_history_events")
    op.drop_table("submittal_references")
    op.drop_index("uq_submittal_reviews_one_official", table_name="submittal_reviews")
    op.drop_table("submittal_reviews")
    op.drop_table("submittal_revisions")
    op.drop_table("submittals")
    op.drop_table("submittal_project_counters")
