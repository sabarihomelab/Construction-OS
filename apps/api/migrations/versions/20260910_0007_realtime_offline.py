"""Create realtime event and offline sync foundation.

Revision ID: 20260910_0007
Revises: 20260910_0006
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0007"
down_revision: str | None = "20260910_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("event_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("entity_version", sa.BigInteger(), nullable=True),
        sa.Column("required_permission_key", sa.String(length=160), nullable=True),
        sa.Column("scope_type", sa.String(length=40), nullable=True),
        sa.Column("scope_id", sa.String(length=160), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "published", "failed", name="outboxeventstatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("event_schema_version >= 1", name="ck_outbox_events_schema_version"),
        sa.CheckConstraint("publish_attempts >= 0", name="ck_outbox_events_publish_attempts"),
        sa.CheckConstraint(
            "entity_version IS NULL OR entity_version >= 1",
            name="ck_outbox_events_entity_version",
        ),
        sa.CheckConstraint(
            "(scope_type IS NULL AND scope_id IS NULL) OR "
            "(scope_type IS NOT NULL AND scope_id IS NOT NULL)",
            name="ck_outbox_events_scope_pair",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_outbox_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_outbox_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["required_permission_key"],
            ["permissions.key"],
            name=op.f("fk_outbox_events_required_permission_key_permissions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_outbox_events_session_id_sessions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
        sa.UniqueConstraint("sequence", name="uq_outbox_events_sequence"),
    )
    op.create_index(op.f("ix_outbox_events_organization_id"), "outbox_events", ["organization_id"])
    op.create_index(op.f("ix_outbox_events_sequence"), "outbox_events", ["sequence"])
    op.create_index(op.f("ix_outbox_events_event_type"), "outbox_events", ["event_type"])
    op.create_index(op.f("ix_outbox_events_entity_type"), "outbox_events", ["entity_type"])
    op.create_index(
        op.f("ix_outbox_events_required_permission_key"),
        "outbox_events",
        ["required_permission_key"],
    )
    op.create_index(op.f("ix_outbox_events_correlation_id"), "outbox_events", ["correlation_id"])
    op.create_index(op.f("ix_outbox_events_status"), "outbox_events", ["status"])
    op.create_index(op.f("ix_outbox_events_available_at"), "outbox_events", ["available_at"])
    op.create_index(
        "ix_outbox_events_org_sequence",
        "outbox_events",
        ["organization_id", "sequence"],
    )
    op.create_index(
        "ix_outbox_events_status_available",
        "outbox_events",
        ["status", "available_at"],
    )

    op.create_table(
        "client_devices",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("web", "pwa", "ios", "android", "desktop", name="deviceplatform", native_enum=False),
            nullable=False,
        ),
        sa.Column("device_label", sa.String(length=160), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=160), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_client_devices_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_client_devices_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_devices")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "installation_id",
            name="uq_client_devices_org_user_installation",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_client_devices_id_org"),
    )
    op.create_index(op.f("ix_client_devices_organization_id"), "client_devices", ["organization_id"])
    op.create_index(op.f("ix_client_devices_user_id"), "client_devices", ["user_id"])
    op.create_index("ix_client_devices_org_user", "client_devices", ["organization_id", "user_id"])

    op.create_table(
        "device_sync_state",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "last_acknowledged_event_sequence", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "last_acknowledged_event_sequence >= 0",
            name="ck_device_sync_state_ack_sequence",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_device_sync_state_revision"),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["client_devices.id", "client_devices.organization_id"],
            name="fk_device_sync_state_device_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("device_id", name=op.f("pk_device_sync_state")),
    )
    op.create_index(op.f("ix_device_sync_state_organization_id"), "device_sync_state", ["organization_id"])

    op.create_table(
        "sync_mutation_receipts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("client_mutation_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column(
            "operation",
            sa.Enum("create", "update", "delete", "action", name="syncmutationoperation", native_enum=False),
            nullable=False,
        ),
        sa.Column("base_version", sa.BigInteger(), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "applied",
                "conflict",
                "rejected",
                name="syncmutationstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="received",
        ),
        sa.Column("server_version", sa.BigInteger(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("length(request_hash) = 64", name="ck_sync_mutation_receipts_hash_length"),
        sa.CheckConstraint(
            "base_version IS NULL OR base_version >= 1",
            name="ck_sync_mutation_receipts_base_version",
        ),
        sa.CheckConstraint(
            "server_version IS NULL OR server_version >= 1",
            name="ck_sync_mutation_receipts_server_version",
        ),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["client_devices.id", "client_devices.organization_id"],
            name="fk_sync_mutation_receipts_device_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_mutation_receipts")),
        sa.UniqueConstraint(
            "organization_id",
            "device_id",
            "client_mutation_id",
            name="uq_sync_mutation_receipts_client_mutation",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_sync_mutation_receipts_id_org"),
    )
    op.create_index(
        op.f("ix_sync_mutation_receipts_organization_id"),
        "sync_mutation_receipts",
        ["organization_id"],
    )
    op.create_index(op.f("ix_sync_mutation_receipts_device_id"), "sync_mutation_receipts", ["device_id"])
    op.create_index(
        op.f("ix_sync_mutation_receipts_entity_type"), "sync_mutation_receipts", ["entity_type"]
    )
    op.create_index(
        "ix_sync_mutation_receipts_org_status",
        "sync_mutation_receipts",
        ["organization_id", "status"],
    )

    op.create_table(
        "sync_conflicts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("mutation_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=False),
        sa.Column("base_version", sa.BigInteger(), nullable=False),
        sa.Column("server_version", sa.BigInteger(), nullable=False),
        sa.Column("client_patch", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("server_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "resolved", "dismissed", name="syncconflictstatus", native_enum=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("resolution", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
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
        sa.CheckConstraint("base_version >= 1", name="ck_sync_conflicts_base_version"),
        sa.CheckConstraint("server_version >= 1", name="ck_sync_conflicts_server_version"),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["client_devices.id", "client_devices.organization_id"],
            name="fk_sync_conflicts_device_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mutation_receipt_id", "organization_id"],
            ["sync_mutation_receipts.id", "sync_mutation_receipts.organization_id"],
            name="fk_sync_conflicts_receipt_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f("fk_sync_conflicts_resolved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_conflicts")),
        sa.UniqueConstraint("mutation_receipt_id", name="uq_sync_conflicts_mutation_receipt"),
    )
    op.create_index(op.f("ix_sync_conflicts_organization_id"), "sync_conflicts", ["organization_id"])
    op.create_index(op.f("ix_sync_conflicts_device_id"), "sync_conflicts", ["device_id"])
    op.create_index(
        "ix_sync_conflicts_org_status", "sync_conflicts", ["organization_id", "status"]
    )
    op.create_index(
        "ix_sync_conflicts_org_entity",
        "sync_conflicts",
        ["organization_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sync_conflicts_org_entity", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_org_status", table_name="sync_conflicts")
    op.drop_index(op.f("ix_sync_conflicts_device_id"), table_name="sync_conflicts")
    op.drop_index(op.f("ix_sync_conflicts_organization_id"), table_name="sync_conflicts")
    op.drop_table("sync_conflicts")

    op.drop_index("ix_sync_mutation_receipts_org_status", table_name="sync_mutation_receipts")
    op.drop_index(op.f("ix_sync_mutation_receipts_entity_type"), table_name="sync_mutation_receipts")
    op.drop_index(op.f("ix_sync_mutation_receipts_device_id"), table_name="sync_mutation_receipts")
    op.drop_index(
        op.f("ix_sync_mutation_receipts_organization_id"), table_name="sync_mutation_receipts"
    )
    op.drop_table("sync_mutation_receipts")

    op.drop_index(op.f("ix_device_sync_state_organization_id"), table_name="device_sync_state")
    op.drop_table("device_sync_state")

    op.drop_index("ix_client_devices_org_user", table_name="client_devices")
    op.drop_index(op.f("ix_client_devices_user_id"), table_name="client_devices")
    op.drop_index(op.f("ix_client_devices_organization_id"), table_name="client_devices")
    op.drop_table("client_devices")

    op.drop_index("ix_outbox_events_status_available", table_name="outbox_events")
    op.drop_index("ix_outbox_events_org_sequence", table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_available_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_status"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_correlation_id"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_required_permission_key"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_entity_type"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_event_type"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_sequence"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_organization_id"), table_name="outbox_events")
    op.drop_table("outbox_events")
