"""Preserve BOQ lineage on purchase order lines.

Revision ID: 20260916_0059
Revises: 20260915_0058
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0059"
down_revision: str | None = "20260915_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_order_lines",
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        """
        UPDATE purchase_order_lines AS pol
        SET boq_item_id = prl.boq_item_id
        FROM purchase_requisition_lines AS prl
        WHERE pol.requisition_line_id = prl.id
          AND pol.project_id = prl.project_id
          AND pol.organization_id = prl.organization_id
          AND prl.boq_item_id IS NOT NULL
        """
    )
    op.create_foreign_key(
        "fk_purchase_order_lines_boq_scope",
        "purchase_order_lines",
        "project_boq_items",
        ["boq_item_id", "project_id", "organization_id"],
        ["id", "project_id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_purchase_order_lines_boq_item_id",
        "purchase_order_lines",
        ["boq_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_order_lines_boq_item_id", table_name="purchase_order_lines")
    op.drop_constraint(
        "fk_purchase_order_lines_boq_scope",
        "purchase_order_lines",
        type_="foreignkey",
    )
    op.drop_column("purchase_order_lines", "boq_item_id")
