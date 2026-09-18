"""Add project material inventory ledger.

Revision ID: 20260911_0046
Revises: 20260911_0045
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0046"
down_revision: str | None = "20260911_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    (
        "materials.inventory.view",
        "inventory",
        "view",
        "View project stock locations, transaction history and derived balances.",
        "medium",
    ),
    (
        "materials.inventory.manage",
        "inventory",
        "manage",
        "Create and manage project material stock locations.",
        "high",
    ),
)


def upgrade() -> None:
    op.create_table(
        "material_stock_locations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "location_type",
            sa.Enum(
                "site_store",
                "work_area",
                "yard",
                "warehouse",
                "other",
                name="stocklocationtype",
                native_enum=False,
            ),
            nullable=False,
            server_default="site_store",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                name="stocklocationstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
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
        sa.CheckConstraint("revision >= 1", name="ck_material_stock_locations_revision"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_material_stock_locations_project_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_material_stock_locations"),
        sa.UniqueConstraint(
            "project_id",
            "code",
            name="uq_material_stock_locations_project_code",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            "organization_id",
            name="uq_material_stock_locations_scope",
        ),
    )
    op.create_index(
        "ix_material_stock_locations_organization_id",
        "material_stock_locations",
        ["organization_id"],
    )
    op.create_index(
        "ix_material_stock_locations_project_id",
        "material_stock_locations",
        ["project_id"],
    )
    op.create_index(
        "ix_material_stock_locations_project_status",
        "material_stock_locations",
        ["project_id", "status"],
    )

    op.create_table(
        "material_stock_transactions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("stock_location_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "opening_balance",
                "grn_receipt",
                "issue",
                "consumption",
                "transfer_in",
                "transfer_out",
                "return_in",
                "return_out",
                "rejection",
                "wastage",
                "damage",
                "adjustment_in",
                "adjustment_out",
                name="stocktransactiontype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "direction",
            sa.Enum(
                "inflow",
                "outflow",
                name="stockdirection",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("unit_code", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "goods_receipt",
                "material_consumption",
                "manual_adjustment",
                name="stocksourcetype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("source_record_id", sa.Uuid(), nullable=False),
        sa.Column("source_parent_id", sa.Uuid(), nullable=True),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("unit_cost_snapshot", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("created_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint("quantity > 0", name="ck_material_stock_transactions_quantity"),
        sa.CheckConstraint(
            "unit_cost_snapshot IS NULL OR unit_cost_snapshot >= 0",
            name="ck_material_stock_transactions_unit_cost",
        ),
        sa.ForeignKeyConstraint(
            ["stock_location_id", "project_id", "organization_id"],
            [
                "material_stock_locations.id",
                "material_stock_locations.project_id",
                "material_stock_locations.organization_id",
            ],
            name="fk_material_stock_transactions_location_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_material_stock_transactions_material_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            [
                "project_wbs_codes.id",
                "project_wbs_codes.project_id",
                "project_wbs_codes.organization_id",
            ],
            name="fk_material_stock_transactions_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            [
                "project_boq_items.id",
                "project_boq_items.project_id",
                "project_boq_items.organization_id",
            ],
            name="fk_material_stock_transactions_boq_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "created_by_membership_id", "organization_id"],
            [
                "project_memberships.project_id",
                "project_memberships.organization_membership_id",
                "project_memberships.organization_id",
            ],
            name="fk_material_stock_transactions_creator_project_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_material_stock_transactions"),
        sa.UniqueConstraint(
            "project_id",
            "source_type",
            "source_record_id",
            "direction",
            name="uq_material_stock_transactions_source_direction",
        ),
    )
    op.create_index(
        "ix_material_stock_transactions_organization_id",
        "material_stock_transactions",
        ["organization_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_project_id",
        "material_stock_transactions",
        ["project_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_stock_location_id",
        "material_stock_transactions",
        ["stock_location_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_material_id",
        "material_stock_transactions",
        ["material_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_wbs_code_id",
        "material_stock_transactions",
        ["wbs_code_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_boq_item_id",
        "material_stock_transactions",
        ["boq_item_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_source_record_id",
        "material_stock_transactions",
        ["source_record_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_source_parent_id",
        "material_stock_transactions",
        ["source_parent_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_project_location_material",
        "material_stock_transactions",
        ["project_id", "stock_location_id", "material_id"],
    )
    op.create_index(
        "ix_material_stock_transactions_project_occurred",
        "material_stock_transactions",
        ["project_id", "occurred_at"],
    )
    op.create_index(
        "ix_material_stock_transactions_source",
        "material_stock_transactions",
        ["source_type", "source_record_id"],
    )

    op.add_column(
        "goods_receipts",
        sa.Column("stock_location_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_goods_receipts_stock_location_id",
        "goods_receipts",
        ["stock_location_id"],
    )
    op.create_foreign_key(
        "fk_goods_receipts_stock_location_scope",
        "goods_receipts",
        "material_stock_locations",
        ["stock_location_id", "project_id", "organization_id"],
        ["id", "project_id", "organization_id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "material_consumptions",
        sa.Column("stock_location_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_material_consumptions_stock_location_id",
        "material_consumptions",
        ["stock_location_id"],
    )
    op.create_foreign_key(
        "fk_material_consumptions_stock_location_scope",
        "material_consumptions",
        "material_stock_locations",
        ["stock_location_id", "project_id", "organization_id"],
        ["id", "project_id", "organization_id"],
        ondelete="RESTRICT",
    )

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String),
        sa.column("module", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.Text),
        sa.column("risk", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": "materials",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _PERMISSIONS]
    op.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys))

    op.drop_constraint(
        "fk_material_consumptions_stock_location_scope",
        "material_consumptions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_material_consumptions_stock_location_id",
        table_name="material_consumptions",
    )
    op.drop_column("material_consumptions", "stock_location_id")

    op.drop_constraint(
        "fk_goods_receipts_stock_location_scope",
        "goods_receipts",
        type_="foreignkey",
    )
    op.drop_index("ix_goods_receipts_stock_location_id", table_name="goods_receipts")
    op.drop_column("goods_receipts", "stock_location_id")

    op.drop_table("material_stock_transactions")
    op.drop_table("material_stock_locations")
