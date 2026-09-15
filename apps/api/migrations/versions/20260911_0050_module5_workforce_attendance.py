"""Add India-first workforce attendance / muster foundation.

Revision ID: 20260911_0050
Revises: 20260911_0049
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0050"
down_revision: str | None = "20260911_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    (
        "workforce.attendance.view",
        "attendance",
        "view",
        "View project daily attendance registers and approved DPR summaries.",
        "medium",
    ),
    (
        "workforce.attendance.create",
        "attendance",
        "create",
        "Create project daily attendance registers from active Worker assignments.",
        "medium",
    ),
    (
        "workforce.attendance.update",
        "attendance",
        "update",
        "Bulk mark and correct draft or rejected project attendance.",
        "high",
    ),
    (
        "workforce.attendance.submit",
        "attendance",
        "submit",
        "Submit completed project attendance under configured approval rules.",
        "high",
    ),
    (
        "workforce.attendance.approve",
        "attendance",
        "approve",
        "Approve or reject project attendance through the configured workflow.",
        "high",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
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
        "workforce_attendance_registers",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("shift_code", sa.String(length=40), nullable=False, server_default="day"),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "in_review",
                "approved",
                "rejected",
                "void",
                name="attendanceregisterstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("prepared_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
        sa.Column(
            "configuration_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_attendance_register_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_attendance_register_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "prepared_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_attendance_register_preparer_project_member_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "approved_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_attendance_register_approver_project_member_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_attendance_register_workflow_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workforce_attendance_registers"),
        sa.UniqueConstraint(
            "project_id",
            "attendance_date",
            "shift_code",
            name="uq_attendance_register_project_date_shift",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_attendance_register_id_org"),
        sa.UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_attendance_register_scope",
        ),
    )
    op.create_index(
        "ix_attendance_register_project_date",
        "workforce_attendance_registers",
        ["project_id", "attendance_date", "shift_code"],
    )
    op.create_index(
        "ix_attendance_register_project_status",
        "workforce_attendance_registers",
        ["project_id", "status", "attendance_date"],
    )
    op.create_index(
        "ix_workforce_attendance_registers_organization_id",
        "workforce_attendance_registers",
        ["organization_id"],
    )
    op.create_index(
        "ix_workforce_attendance_registers_project_id",
        "workforce_attendance_registers",
        ["project_id"],
    )

    op.create_table(
        "workforce_attendance_entries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("register_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("crew_id", sa.Uuid(), nullable=True),
        sa.Column("employer_party_id", sa.Uuid(), nullable=True),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column(
            "engagement_type",
            sa.Enum(
                "staff",
                "direct_labour",
                "contract_labour",
                "subcontractor_labour",
                "vendor_crew",
                "other",
                name="workerengagementtype",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("trade", sa.String(length=120), nullable=True),
        sa.Column(
            "mark_status",
            sa.Enum(
                "not_marked",
                "present",
                "absent",
                "half_day",
                "leave",
                "weekly_off",
                name="attendancemarkstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="not_marked",
        ),
        sa.Column("regular_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(length=160), nullable=True),
        sa.Column(
            "context_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("regular_hours >= 0", name="ck_attendance_entry_regular_hours"),
        sa.CheckConstraint("overtime_hours >= 0", name="ck_attendance_entry_overtime_hours"),
        sa.CheckConstraint(
            "regular_hours + overtime_hours <= 24",
            name="ck_attendance_entry_total_hours",
        ),
        sa.ForeignKeyConstraint(
            ["register_id", "project_id", "organization_id"],
            [
                "workforce_attendance_registers.id",
                "workforce_attendance_registers.project_id",
                "workforce_attendance_registers.organization_id",
            ],
            name="fk_attendance_entry_register_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "project_id", "organization_id"],
            [
                "project_worker_assignments.id",
                "project_worker_assignments.project_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_attendance_entry_assignment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "worker_id", "organization_id"],
            [
                "project_worker_assignments.project_id",
                "project_worker_assignments.worker_id",
                "project_worker_assignments.organization_id",
            ],
            name="fk_attendance_entry_worker_assignment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["crew_id", "organization_id"],
            ["crews.id", "crews.organization_id"],
            name="fk_attendance_entry_crew_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employer_party_id", "organization_id"],
            ["commercial_parties.id", "commercial_parties.organization_id"],
            name="fk_attendance_entry_employer_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_attendance_entry_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workforce_attendance_entries"),
        sa.UniqueConstraint(
            "register_id",
            "worker_id",
            name="uq_attendance_entry_register_worker",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_attendance_entry_id_org"),
    )
    op.create_index(
        "ix_attendance_entry_register_status",
        "workforce_attendance_entries",
        ["register_id", "mark_status"],
    )
    op.create_index(
        "ix_attendance_entry_worker_date",
        "workforce_attendance_entries",
        ["worker_id", "register_id"],
    )
    op.create_index(
        "ix_attendance_entry_wbs",
        "workforce_attendance_entries",
        ["project_id", "wbs_code_id"],
    )
    op.create_index(
        "ix_attendance_entry_employer",
        "workforce_attendance_entries",
        ["project_id", "employer_party_id"],
    )

    op.create_table(
        "workforce_attendance_history_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("register_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "created",
                "populated",
                "updated",
                "submitted",
                "approved",
                "rejected",
                "reopened",
                "voided",
                name="attendancehistorytype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("register_revision", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("register_revision >= 1", name="ck_attendance_history_revision"),
        sa.ForeignKeyConstraint(
            ["register_id", "organization_id"],
            ["workforce_attendance_registers.id", "workforce_attendance_registers.organization_id"],
            name="fk_attendance_history_register_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_attendance_history_actor_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workforce_attendance_history_events"),
    )
    op.create_index(
        "ix_attendance_history_register",
        "workforce_attendance_history_events",
        ["register_id", "created_at"],
    )

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String),
        sa.column("module", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.Text),
        sa.column("risk", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": "workforce",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(
        sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys)
    )
    op.drop_table("workforce_attendance_history_events")
    op.drop_table("workforce_attendance_entries")
    op.drop_table("workforce_attendance_registers")
