"""Add project material consumption records.

Revision ID: 20260911_0043
Revises: 20260911_0042
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0043"
down_revision: str | None = "20260911_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_consumptions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("consumption_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("unit_code", sa.String(40), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("cost_basis", sa.String(120), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "posted",
                "reversed",
                name="materialconsumptionstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("posted_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint("quantity > 0", name="ck_material_consumptions_quantity"),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_material_consumptions_unit_cost",
        ),
        sa.CheckConstraint(
            "total_cost IS NULL OR total_cost >= 0",
            name="ck_material_consumptions_total_cost",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_material_consumptions_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_material_consumptions_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_material_consumptions_material_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_material_consumptions_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_material_consumptions_boq_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_consumptions_creator_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "posted_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_consumptions_poster_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "reversed_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_consumptions_reverser_project_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_material_consumptions"),
        sa.UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_material_consumptions_scope",
        ),
    )
    op.create_index(
        "ix_material_consumptions_organization_id",
        "material_consumptions",
        ["organization_id"],
    )
    op.create_index(
        "ix_material_consumptions_material_id",
        "material_consumptions",
        ["material_id"],
    )
    op.create_index(
        "ix_material_consumptions_wbs_code_id",
        "material_consumptions",
        ["wbs_code_id"],
    )
    op.create_index(
        "ix_material_consumptions_boq_item_id",
        "material_consumptions",
        ["boq_item_id"],
    )
    op.create_index(
        "ix_material_consumptions_project_date",
        "material_consumptions",
        ["project_id", "consumption_date"],
    )
    op.create_index(
        "ix_material_consumptions_project_material",
        "material_consumptions",
        ["project_id", "material_id"],
    )
    op.create_index(
        "ix_material_consumptions_project_status",
        "material_consumptions",
        ["project_id", "status"],
    )
    op.alter_column(
        "project_cost_allocations",
        "quantity",
        existing_type=sa.Numeric(18, 3),
        type_=sa.Numeric(20, 4),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "project_cost_allocations",
        "quantity",
        existing_type=sa.Numeric(20, 4),
        type_=sa.Numeric(18, 3),
        existing_nullable=True,
    )
    op.drop_table("material_consumptions")
