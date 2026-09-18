"""Add purchase order commitment allocations.

Revision ID: 20260911_0045
Revises: 20260911_0044
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0045"
down_revision: str | None = "20260911_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_commitment_allocations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("commitment_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("source_line_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("unit_code", sa.String(40), nullable=False),
        sa.Column("committed_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False),
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
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_project_commitment_allocations_quantity",
        ),
        sa.CheckConstraint(
            "committed_amount >= 0",
            name="ck_project_commitment_allocations_committed_amount",
        ),
        sa.CheckConstraint(
            "tax_amount >= 0",
            name="ck_project_commitment_allocations_tax_amount",
        ),
        sa.CheckConstraint(
            "gross_amount >= 0",
            name="ck_project_commitment_allocations_gross_amount",
        ),
        sa.CheckConstraint(
            "gross_amount = committed_amount + tax_amount",
            name="ck_project_commitment_allocations_amount_reconciliation",
        ),
        sa.ForeignKeyConstraint(
            ["commitment_id", "project_id", "organization_id"],
            [
                "project_commitments.id",
                "project_commitments.project_id",
                "project_commitments.organization_id",
            ],
            name="fk_project_commitment_allocations_commitment_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_line_id", "project_id", "organization_id"],
            [
                "purchase_order_lines.id",
                "purchase_order_lines.project_id",
                "purchase_order_lines.organization_id",
            ],
            name="fk_project_commitment_allocations_po_line_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_project_commitment_allocations_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_project_commitment_allocations_boq_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_project_commitment_allocations_material_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_commitment_allocations"),
        sa.UniqueConstraint(
            "commitment_id",
            "line_number",
            name="uq_project_commitment_allocations_line",
        ),
        sa.UniqueConstraint(
            "commitment_id",
            "source_line_id",
            name="uq_project_commitment_allocations_source_line",
        ),
    )
    op.create_index(
        "ix_project_commitment_allocations_organization_id",
        "project_commitment_allocations",
        ["organization_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_project_id",
        "project_commitment_allocations",
        ["project_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_commitment_id",
        "project_commitment_allocations",
        ["commitment_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_source_line_id",
        "project_commitment_allocations",
        ["source_line_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_wbs_code_id",
        "project_commitment_allocations",
        ["wbs_code_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_boq_item_id",
        "project_commitment_allocations",
        ["boq_item_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_material_id",
        "project_commitment_allocations",
        ["material_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_project_wbs",
        "project_commitment_allocations",
        ["project_id", "wbs_code_id"],
    )
    op.create_index(
        "ix_project_commitment_allocations_project_material",
        "project_commitment_allocations",
        ["project_id", "material_id"],
    )


def downgrade() -> None:
    op.drop_table("project_commitment_allocations")
