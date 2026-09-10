"""Add Meetings foundation.

Revision ID: 20260910_0034
Revises: 20260910_0033
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0034"
down_revision: str | None = "20260910_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("meetings.meeting.view", "meeting", "view", "View meetings, minutes, attendees, agenda and references in authorized projects.", "medium"),
    ("meetings.meeting.create", "meeting", "create", "Create project meetings.", "medium"),
    ("meetings.meeting.update", "meeting", "update", "Update non-finalized project meetings.", "medium"),
    ("meetings.meeting.manage", "meeting", "manage", "Cancel and administratively manage project meetings.", "high"),
    ("meetings.series.manage", "series", "manage", "Create and manage recurring meeting series.", "medium"),
    ("meetings.attendee.manage", "attendee", "manage", "Manage meeting attendees and attendance.", "medium"),
    ("meetings.agenda.manage", "agenda", "manage", "Manage meeting agenda items.", "medium"),
    ("meetings.action.view", "action", "view", "View assigned and project meeting action items.", "medium"),
    ("meetings.action.manage", "action", "manage", "Create, assign and update meeting action items.", "medium"),
    ("meetings.reference.manage", "reference", "manage", "Link permitted project records to meetings.", "medium"),
    ("meetings.minutes.manage", "minutes", "manage", "Draft and revise meeting minutes before finalization.", "medium"),
    ("meetings.minutes.finalize", "minutes", "finalize", "Finalize meeting minutes under configured approval rules.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "meeting_project_counters",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.BigInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("next_number >= 1", name="ck_meeting_counter_next"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_meeting_counter_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id", "project_id", name="pk_meeting_project_counters"),
    )

    op.create_table(
        "meeting_series",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("default_location", sa.String(255), nullable=True),
        sa.Column("recurrence_rule", sa.String(500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_meeting_series_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_meeting_series_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_meeting_series"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_meeting_series_id_project_org"),
        sa.UniqueConstraint("project_id", "name", name="uq_meeting_series_project_name"),
    )
    op.create_index("ix_meeting_series_org", "meeting_series", ["organization_id"])
    op.create_index("ix_meeting_series_project", "meeting_series", ["project_id"])
    op.create_index("ix_meeting_series_project_active", "meeting_series", ["project_id", "active"])

    op.create_table(
        "meetings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("draft", "scheduled", "in_progress", "completed", "cancelled", name="meetingstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("organizer_membership_id", sa.Uuid(), nullable=False),
        sa.Column("minutes", sa.Text(), nullable=True),
        sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("number >= 1", name="ck_meetings_number"),
        sa.CheckConstraint("revision >= 1", name="ck_meetings_revision"),
        sa.CheckConstraint("end_at IS NULL OR end_at >= start_at", name="ck_meetings_date_range"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_meetings_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_id", "project_id", "organization_id"], ["meeting_series.id", "meeting_series.project_id", "meeting_series.organization_id"], name="fk_meetings_series_project_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id", "organizer_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_meetings_organizer_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workflow_instance_id", "organization_id"], ["workflow_instances.id", "workflow_instances.organization_id"], name="fk_meetings_workflow_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_meetings"),
        sa.UniqueConstraint("project_id", "number", name="uq_meetings_project_number"),
        sa.UniqueConstraint("id", "project_id", "organization_id", name="uq_meetings_id_project_org"),
    )
    op.create_index("ix_meetings_org", "meetings", ["organization_id"])
    op.create_index("ix_meetings_project", "meetings", ["project_id"])
    op.create_index("ix_meetings_start", "meetings", ["start_at"])
    op.create_index("ix_meetings_project_status", "meetings", ["project_id", "status", "start_at"])

    op.create_table(
        "meeting_attendees",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=True),
        sa.Column("external_name", sa.String(255), nullable=True),
        sa.Column("external_email", sa.String(320), nullable=True),
        sa.Column("role", sa.String(120), nullable=True),
        sa.Column("attendance_status", sa.Enum("invited", "accepted", "declined", "attended", "absent", name="attendancestatus", native_enum=False), nullable=False, server_default="invited"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("membership_id IS NOT NULL OR external_name IS NOT NULL", name="ck_meeting_attendee_identity"),
        sa.CheckConstraint("revision >= 1", name="ck_meeting_attendee_revision"),
        sa.ForeignKeyConstraint(["meeting_id", "project_id", "organization_id"], ["meetings.id", "meetings.project_id", "meetings.organization_id"], name="fk_meeting_attendee_meeting_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_meeting_attendee_member_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meeting_attendees"),
        sa.UniqueConstraint("meeting_id", "membership_id", name="uq_meeting_attendee_internal"),
    )
    op.create_index("ix_meeting_attendee_org", "meeting_attendees", ["organization_id"])
    op.create_index("ix_meeting_attendee_project", "meeting_attendees", ["project_id"])
    op.create_index("ix_meeting_attendee_meeting", "meeting_attendees", ["meeting_id"])

    op.create_table(
        "meeting_agenda_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_membership_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("open", "discussed", "deferred", "closed", name="agendaitemstatus", native_enum=False), nullable=False, server_default="open"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_meeting_agenda_sequence"),
        sa.CheckConstraint("revision >= 1", name="ck_meeting_agenda_revision"),
        sa.ForeignKeyConstraint(["meeting_id", "project_id", "organization_id"], ["meetings.id", "meetings.project_id", "meetings.organization_id"], name="fk_meeting_agenda_meeting_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "owner_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_meeting_agenda_owner_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meeting_agenda_items"),
        sa.UniqueConstraint("meeting_id", "sequence", name="uq_meeting_agenda_sequence"),
    )
    op.create_index("ix_meeting_agenda_org", "meeting_agenda_items", ["organization_id"])
    op.create_index("ix_meeting_agenda_project", "meeting_agenda_items", ["project_id"])
    op.create_index("ix_meeting_agenda_meeting", "meeting_agenda_items", ["meeting_id"])

    op.create_table(
        "meeting_action_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assignee_membership_id", sa.Uuid(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("open", "in_progress", "completed", "cancelled", name="meetingactionstatus", native_enum=False), nullable=False, server_default="open"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_meeting_action_sequence"),
        sa.CheckConstraint("revision >= 1", name="ck_meeting_action_revision"),
        sa.ForeignKeyConstraint(["meeting_id", "project_id", "organization_id"], ["meetings.id", "meetings.project_id", "meetings.organization_id"], name="fk_meeting_action_meeting_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "assignee_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_meeting_action_assignee_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meeting_action_items"),
        sa.UniqueConstraint("meeting_id", "sequence", name="uq_meeting_action_sequence"),
    )
    op.create_index("ix_meeting_action_org", "meeting_action_items", ["organization_id"])
    op.create_index("ix_meeting_action_project", "meeting_action_items", ["project_id"])
    op.create_index("ix_meeting_action_meeting", "meeting_action_items", ["meeting_id"])
    op.create_index("ix_meeting_action_project_status", "meeting_action_items", ["project_id", "status", "due_at"])

    op.create_table(
        "meeting_references",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("reference_type", sa.Enum("rfi", "submittal", "document", "drawing", "other", name="meetingreferencetype", native_enum=False), nullable=False),
        sa.Column("reference_id", sa.String(160), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["meeting_id", "project_id", "organization_id"], ["meetings.id", "meetings.project_id", "meetings.organization_id"], name="fk_meeting_reference_meeting_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_meeting_references"),
        sa.UniqueConstraint("meeting_id", "reference_type", "reference_id", name="uq_meeting_reference_target"),
    )
    op.create_index("ix_meeting_reference_org", "meeting_references", ["organization_id"])
    op.create_index("ix_meeting_reference_project", "meeting_references", ["project_id"])
    op.create_index("ix_meeting_reference_meeting", "meeting_references", ["meeting_id"])

    op.create_table(
        "meeting_history_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Enum("created", "updated", "started", "minutes_updated", "finalized", "cancelled", "attendee_changed", "agenda_changed", "action_changed", "reference_changed", name="meetinghistorytype", native_enum=False), nullable=False),
        sa.Column("meeting_revision", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["meeting_id", "project_id", "organization_id"], ["meetings.id", "meetings.project_id", "meetings.organization_id"], name="fk_meeting_history_meeting_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_meeting_history_events"),
    )
    op.create_index("ix_meeting_history_org", "meeting_history_events", ["organization_id"])
    op.create_index("ix_meeting_history_project", "meeting_history_events", ["project_id"])
    op.create_index("ix_meeting_history_meeting", "meeting_history_events", ["meeting_id"])
    op.create_index("ix_meeting_history_meeting_created", "meeting_history_events", ["meeting_id", "created_at"])

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
                "module": "meetings",
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
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(permissions.delete().where(permissions.c.key.in_([key for key, *_ in _PERMISSIONS])))
    op.drop_table("meeting_history_events")
    op.drop_table("meeting_references")
    op.drop_table("meeting_action_items")
    op.drop_table("meeting_agenda_items")
    op.drop_table("meeting_attendees")
    op.drop_table("meetings")
    op.drop_table("meeting_series")
    op.drop_table("meeting_project_counters")
