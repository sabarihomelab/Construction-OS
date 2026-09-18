"""Extend project commitment allocations for subcontract lines.

Revision ID: 20260916_0060
Revises: 20260916_0059
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0060"
down_revision: str | None = "20260916_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "project_commitment_allocations",
        "source_line_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.add_column(
        "project_commitment_allocations",
        sa.Column("subcontract_line_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_commitment_allocations_subcontract_line_scope",
        "project_commitment_allocations",
        "subcontract_lines",
        ["subcontract_line_id", "project_id", "organization_id"],
        ["id", "project_id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_project_commitment_allocations_subcontract_line",
        "project_commitment_allocations",
        ["commitment_id", "subcontract_line_id"],
    )
    op.create_check_constraint(
        "ck_project_commitment_allocations_source_line_choice",
        "project_commitment_allocations",
        "(source_line_id IS NOT NULL AND subcontract_line_id IS NULL) OR "
        "(source_line_id IS NULL AND subcontract_line_id IS NOT NULL)",
    )
    op.create_index(
        "ix_project_commitment_allocations_subcontract_line_id",
        "project_commitment_allocations",
        ["subcontract_line_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_commitment_allocations_subcontract_line_id",
        table_name="project_commitment_allocations",
    )
    op.drop_constraint(
        "ck_project_commitment_allocations_source_line_choice",
        "project_commitment_allocations",
        type_="check",
    )
    op.drop_constraint(
        "uq_project_commitment_allocations_subcontract_line",
        "project_commitment_allocations",
        type_="unique",
    )
    op.drop_constraint(
        "fk_project_commitment_allocations_subcontract_line_scope",
        "project_commitment_allocations",
        type_="foreignkey",
    )
    op.drop_column("project_commitment_allocations", "subcontract_line_id")
    op.alter_column(
        "project_commitment_allocations",
        "source_line_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
