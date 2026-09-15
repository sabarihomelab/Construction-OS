"""Create admin operations telemetry foundation.

Revision ID: 20260910_0017
Revises: 20260910_0016
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0017"
down_revision: str | None = "20260910_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_health_snapshots",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("component_key", sa.String(length=140), nullable=False),
        sa.Column("state", sa.Enum("healthy", "attention", "degraded", "critical", "unknown", name="healthstate", native_enum=False), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operational_health_snapshots_org_component_time", "operational_health_snapshots", ["organization_id", "category", "component_key", "observed_at"])

    op.create_table(
        "operational_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.Enum("healthy", "attention", "degraded", "critical", "unknown", name="operationaleventseverity", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("open", "resolved", name="operationaleventstatus", native_enum=False), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_key", sa.String(length=140), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("occurrence_count", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_summary", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operational_events_org_status", "operational_events", ["organization_id", "status", "severity"])
    op.create_index("ix_operational_events_org_key", "operational_events", ["organization_id", "event_key", "last_seen_at"])

    op.create_table(
        "operations_retention_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("snapshot_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("event_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("snapshot_days >= 1", name="ck_operations_retention_snapshot_days"),
        sa.CheckConstraint("event_days >= 1", name="ck_operations_retention_event_days"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "category", name="uq_operations_retention_org_category"),
    )


def downgrade() -> None:
    op.drop_table("operations_retention_policies")
    op.drop_table("operational_events")
    op.drop_table("operational_health_snapshots")
