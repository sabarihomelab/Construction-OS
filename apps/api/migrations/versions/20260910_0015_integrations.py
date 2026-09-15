"""Create integration, staging and reconciliation foundation.

Revision ID: 20260910_0015
Revises: 20260910_0014
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0015"
down_revision: str | None = "20260910_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_connectors",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.Enum("active", "disabled", "degraded", "auth_required", name="connectorstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("credential_reference", sa.String(length=255), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_summary", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_integration_connectors_org_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_integration_connectors_id_org"),
    )
    op.create_index("ix_integration_connectors_org_status", "integration_connectors", ["organization_id", "status"])

    op.create_table(
        "ingestion_batches",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("external_batch_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Enum("received", "validating", "staged", "processing", "ready_to_commit", "committed", "quarantined", "retrying", "failed", name="ingestionstatus", native_enum=False), nullable=False, server_default="received"),
        sa.Column("mapping_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("received_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("invalid_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("committed_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("received_count >= 0", name="ck_ingestion_batches_received_count"),
        sa.CheckConstraint("valid_count >= 0", name="ck_ingestion_batches_valid_count"),
        sa.CheckConstraint("invalid_count >= 0", name="ck_ingestion_batches_invalid_count"),
        sa.CheckConstraint("committed_count >= 0", name="ck_ingestion_batches_committed_count"),
        sa.ForeignKeyConstraint(["connector_id", "organization_id"], ["integration_connectors.id", "integration_connectors.organization_id"], name="fk_ingestion_batches_connector_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "connector_id", "idempotency_key", name="uq_ingestion_batches_idempotency"),
        sa.UniqueConstraint("id", "organization_id", name="uq_ingestion_batches_id_org"),
    )
    op.create_index("ix_ingestion_batches_org_status", "ingestion_batches", ["organization_id", "status"])

    op.create_table(
        "staged_external_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("external_type", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Enum("staged", "valid", "invalid", "mapped", "committed", "quarantined", name="stagedrecordstatus", native_enum=False), nullable=False, server_default="staged"),
        sa.Column("mapping_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("canonical_entity_type", sa.String(length=120), nullable=True),
        sa.Column("canonical_entity_id", sa.String(length=160), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(payload_checksum) = 64", name="ck_staged_external_records_checksum"),
        sa.ForeignKeyConstraint(["batch_id", "organization_id"], ["ingestion_batches.id", "ingestion_batches.organization_id"], name="fk_staged_external_records_batch_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "external_type", "external_id", name="uq_staged_external_records_identity"),
    )
    op.create_index("ix_staged_external_records_batch_status", "staged_external_records", ["batch_id", "status"])

    op.create_table(
        "external_record_mappings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("external_type", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("internal_type", sa.String(length=120), nullable=False),
        sa.Column("internal_id", sa.String(length=160), nullable=False),
        sa.Column("reconciliation_status", sa.Enum("current", "changed", "conflict", "missing_source", name="reconciliationstatus", native_enum=False), nullable=False, server_default="current"),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(source_checksum) = 64", name="ck_external_record_mappings_checksum"),
        sa.ForeignKeyConstraint(["connector_id", "organization_id"], ["integration_connectors.id", "integration_connectors.organization_id"], name="fk_external_record_mappings_connector_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "connector_id", "external_type", "external_id", name="uq_external_record_mappings_source"),
    )
    op.create_index("ix_external_record_mappings_internal", "external_record_mappings", ["organization_id", "internal_type", "internal_id"])


def downgrade() -> None:
    op.drop_table("external_record_mappings")
    op.drop_table("staged_external_records")
    op.drop_table("ingestion_batches")
    op.drop_table("integration_connectors")
