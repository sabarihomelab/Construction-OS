"""Harden client receipt reversal lineage.

Revision ID: 20260918_0064
Revises: 20260916_0063
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260918_0064"
down_revision: str | None = "20260916_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_client_receipts_scope",
        "client_receipts",
        ["id", "project_id", "organization_id"],
    )
    op.drop_constraint(
        "fk_client_receipts_reversal_org",
        "client_receipts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_client_receipts_reversal_scope",
        "client_receipts",
        "client_receipts",
        ["reversal_of_receipt_id", "project_id", "organization_id"],
        ["id", "project_id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_client_receipts_reversal_once",
        "client_receipts",
        ["reversal_of_receipt_id", "project_id", "organization_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_client_receipts_reversal_once",
        "client_receipts",
        type_="unique",
    )
    op.drop_constraint(
        "fk_client_receipts_reversal_scope",
        "client_receipts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_client_receipts_reversal_org",
        "client_receipts",
        "client_receipts",
        ["reversal_of_receipt_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "uq_client_receipts_scope",
        "client_receipts",
        type_="unique",
    )
