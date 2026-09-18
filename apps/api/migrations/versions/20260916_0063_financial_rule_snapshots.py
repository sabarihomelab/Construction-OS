"""Add effective financial rule snapshot storage.

Revision ID: 20260916_0063
Revises: 20260916_0062
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260916_0063"
down_revision: str | None = "20260916_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_rule_snapshots",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(160), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_financial_rule_snapshots_project_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_financial_rule_snapshots"),
        sa.UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            "rule_key",
            name="uq_financial_rule_snapshots_entity_rule",
        ),
    )
    op.create_index(
        "ix_financial_rule_snapshots_organization_id",
        "financial_rule_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "ix_financial_rule_snapshots_project_id",
        "financial_rule_snapshots",
        ["project_id"],
    )
    op.create_index(
        "ix_financial_rule_snapshots_entity_id",
        "financial_rule_snapshots",
        ["entity_id"],
    )
    op.create_index(
        "ix_financial_rule_snapshots_project_entity",
        "financial_rule_snapshots",
        ["project_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_rule_snapshots_project_entity", table_name="financial_rule_snapshots")
    op.drop_index("ix_financial_rule_snapshots_entity_id", table_name="financial_rule_snapshots")
    op.drop_index("ix_financial_rule_snapshots_project_id", table_name="financial_rule_snapshots")
    op.drop_index("ix_financial_rule_snapshots_organization_id", table_name="financial_rule_snapshots")
    op.drop_table("financial_rule_snapshots")
