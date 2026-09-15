"""Add project-scoped RFI management.

Revision ID: 20260910_0026
Revises: 20260910_0025
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0026"
down_revision: str | None = "20260910_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RFI_PERMISSIONS = (
    (
        "rfis.rfi.view",
        "rfis",
        "rfi",
        "view",
        "View RFIs, responses, references and history in the authorized project scope.",
        "medium",
    ),
    (
        "rfis.rfi.create",
        "rfis",
        "rfi",
        "create",
        "Create draft RFIs in the authorized project scope.",
        "medium",
    ),
    (
        "rfis.rfi.update",
        "rfis",
        "rfi",
        "update",
        "Edit and open RFIs and add controlled references in the authorized project scope.",
        "medium",
    ),
    (
        "rfis.rfi.respond",
        "rfis",
        "rfi",
        "respond",
        "Add proposed or official RFI responses in the authorized project scope.",
        "high",
    ),
    (
        "rfis.rfi.close",
        "rfis",
        "rfi",
        "close",
        "Close answered RFIs in the authorized project scope.",
        "high",
    ),
    (
        "rfis.rfi.manage",
        "rfis",
        "rfi",
        "manage",
        "Manage RFI responsibility and controlled void actions.",
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
        "rfi_project_counters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "next_number >= 1",
            name="ck_rfi_project_counters_next_number",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_rfi_project_counters_project_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name="pk_rfi_project_counters"),
        sa.UniqueConstraint("project_id", name="uq_rfi_project_counters_project"),
    )
    op.create_index(
        "ix_rfi_project_counters_organization_id",
        "rfi_project_counters",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "rfis",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "open",
                "answered",
                "closed",
                "void",
                name="rfistatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("priority", sa.String(length=40), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("ball_in_court_membership_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_rfis_version"),
        sa.CheckConstraint("number >= 1", name="ck_rfis_number"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_rfis_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ball_in_court_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_rfis_ball_in_court_membership_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_rfis_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfis"),
        sa.UniqueConstraint("id", "organization_id", name="uq_rfis_id_org"),
        sa.UniqueConstraint("project_id", "number", name="uq_rfis_project_number"),
    )
    op.create_index("ix_rfis_organization_id", "rfis", ["organization_id"], unique=False)
    op.create_index("ix_rfis_project_id", "rfis", ["project_id"], unique=False)
    op.create_index(
        "ix_rfis_project_status_due",
        "rfis",
        ["project_id", "status", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_rfis_project_ball_in_court",
        "rfis",
        ["project_id", "ball_in_court_membership_id"],
        unique=False,
    )

    op.create_table(
        "rfi_responses",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("rfi_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "proposed",
                "official",
                "superseded",
                "withdrawn",
                name="rfiresponsestatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("responded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("official_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_rfi_responses_sequence"),
        sa.ForeignKeyConstraint(
            ["rfi_id", "organization_id"],
            ["rfis.id", "rfis.organization_id"],
            name="fk_rfi_responses_rfi_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["responded_by_user_id"],
            ["users.id"],
            name="fk_rfi_responses_responded_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfi_responses"),
        sa.UniqueConstraint("id", "organization_id", name="uq_rfi_responses_id_org"),
        sa.UniqueConstraint("rfi_id", "sequence", name="uq_rfi_responses_rfi_sequence"),
    )
    op.create_index("ix_rfi_responses_organization_id", "rfi_responses", ["organization_id"])
    op.create_index("ix_rfi_responses_rfi_id", "rfi_responses", ["rfi_id"])
    op.create_index(
        "ix_rfi_responses_rfi_status",
        "rfi_responses",
        ["rfi_id", "status"],
    )

    op.create_table(
        "rfi_references",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("rfi_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reference_type",
            sa.Enum(
                "drawing_revision",
                "specification_section",
                "document_revision",
                "schedule_activity",
                "change_event",
                "custom",
                name="rfireferencetype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reference_id", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["rfi_id", "organization_id"],
            ["rfis.id", "rfis.organization_id"],
            name="fk_rfi_references_rfi_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfi_references"),
        sa.UniqueConstraint(
            "rfi_id",
            "reference_type",
            "reference_id",
            name="uq_rfi_references_target",
        ),
    )
    op.create_index("ix_rfi_references_organization_id", "rfi_references", ["organization_id"])
    op.create_index("ix_rfi_references_rfi_id", "rfi_references", ["rfi_id"])
    op.create_index(
        "ix_rfi_references_target",
        "rfi_references",
        ["organization_id", "reference_type", "reference_id"],
    )

    op.create_table(
        "rfi_history_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("rfi_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "created",
                "opened",
                "updated",
                "response_added",
                "official_response_set",
                "ball_in_court_changed",
                "closed",
                "voided",
                name="rfihistorytype",
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
            name="ck_rfi_history_entity_version",
        ),
        sa.ForeignKeyConstraint(
            ["rfi_id", "organization_id"],
            ["rfis.id", "rfis.organization_id"],
            name="fk_rfi_history_rfi_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_rfi_history_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfi_history_events"),
    )
    op.create_index("ix_rfi_history_events_organization_id", "rfi_history_events", ["organization_id"])
    op.create_index("ix_rfi_history_events_rfi_id", "rfi_history_events", ["rfi_id"])
    op.create_index(
        "ix_rfi_history_rfi_created",
        "rfi_history_events",
        ["rfi_id", "created_at"],
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
            for key, module, resource, action, description, risk in _RFI_PERMISSIONS
        ],
    )


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in _RFI_PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")
    op.drop_table("rfi_history_events")
    op.drop_table("rfi_references")
    op.drop_table("rfi_responses")
    op.drop_table("rfis")
    op.drop_table("rfi_project_counters")
