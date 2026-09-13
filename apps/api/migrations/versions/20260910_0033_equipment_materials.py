"""Add Equipment and Materials foundation.

Revision ID: 20260910_0033
Revises: 20260910_0032
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0033"
down_revision: str | None = "20260910_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("equipment.module.view", "module", "view", "Access Equipment and Materials within permitted company and projects.", "medium"),
    ("equipment.asset.view", "asset", "view", "View company equipment assets.", "medium"),
    ("equipment.asset.manage", "asset", "manage", "Create, update and retire company equipment assets.", "high"),
    ("equipment.assignment.view", "assignment", "view", "View project equipment assignments.", "medium"),
    ("equipment.assignment.manage", "assignment", "manage", "Assign and release equipment within authorized projects.", "high"),
    ("equipment.maintenance.view", "maintenance", "view", "View equipment maintenance records.", "medium"),
    ("equipment.maintenance.manage", "maintenance", "manage", "Create and manage equipment maintenance records.", "high"),
    ("materials.material.view", "material", "view", "View the company material catalog.", "medium"),
    ("materials.material.manage", "material", "manage", "Create, update and retire material catalog records.", "high"),
    ("materials.plan.view", "material_plan", "view", "View planned project material quantities.", "medium"),
    ("materials.plan.manage", "material_plan", "manage", "Create and revise project material plans.", "high"),
    ("materials.delivery.view", "delivery", "view", "View project material deliveries.", "medium"),
    ("materials.delivery.manage", "delivery", "manage", "Create, receive, reject and correct project material deliveries.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "equipment_assets",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("asset_number", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("make", sa.String(120), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("serial_number", sa.String(160), nullable=True),
        sa.Column("ownership", sa.Enum("owned", "rented", "leased", "subcontractor", name="equipmentownership", native_enum=False), nullable=False, server_default="owned"),
        sa.Column("status", sa.Enum("available", "assigned", "maintenance", "out_of_service", "retired", name="equipmentstatus", native_enum=False), nullable=False, server_default="available"),
        sa.Column("meter_unit", sa.String(40), nullable=True),
        sa.Column("current_meter", sa.Numeric(18, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_equipment_assets_revision"),
        sa.CheckConstraint("current_meter IS NULL OR current_meter >= 0", name="ck_equipment_assets_meter"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_equipment_assets_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_equipment_assets"),
        sa.UniqueConstraint("organization_id", "asset_number", name="uq_equipment_assets_org_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_equipment_assets_id_org"),
    )
    op.create_index("ix_equipment_assets_org", "equipment_assets", ["organization_id"])
    op.create_index("ix_equipment_assets_number", "equipment_assets", ["asset_number"])
    op.create_index("ix_equipment_assets_org_status", "equipment_assets", ["organization_id", "status"])
    op.create_index("ix_equipment_assets_org_category", "equipment_assets", ["organization_id", "category"])

    op.create_table(
        "project_equipment_assignments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_asset_id", sa.Uuid(), nullable=False),
        sa.Column("operator_worker_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("active", "ended", name="equipmentassignmentstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("starting_meter", sa.Numeric(18, 4), nullable=True),
        sa.Column("ending_meter", sa.Numeric(18, 4), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_equipment_assign_revision"),
        sa.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_equipment_assign_dates"),
        sa.CheckConstraint("starting_meter IS NULL OR starting_meter >= 0", name="ck_equipment_assign_start_meter"),
        sa.CheckConstraint("ending_meter IS NULL OR ending_meter >= 0", name="ck_equipment_assign_end_meter"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_equipment_assign_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_asset_id", "organization_id"], ["equipment_assets.id", "equipment_assets.organization_id"], name="fk_equipment_assign_asset_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operator_worker_id", "organization_id"], ["workers.id", "workers.organization_id"], name="fk_equipment_assign_worker_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_equipment_assignments"),
        sa.UniqueConstraint("project_id", "equipment_asset_id", "start_date", name="uq_equipment_assign_project_asset_start"),
        sa.UniqueConstraint("id", "organization_id", name="uq_equipment_assign_id_org"),
    )
    op.create_index("ix_equipment_assign_org", "project_equipment_assignments", ["organization_id"])
    op.create_index("ix_equipment_assign_project", "project_equipment_assignments", ["project_id"])
    op.create_index("ix_equipment_assign_asset", "project_equipment_assignments", ["equipment_asset_id"])
    op.create_index("ix_equipment_assign_project_status", "project_equipment_assignments", ["project_id", "status"])

    op.create_table(
        "equipment_maintenance",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_asset_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("maintenance_type", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("scheduled", "in_progress", "completed", "cancelled", name="maintenancestatus", native_enum=False), nullable=False, server_default="scheduled"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meter_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("meter_unit", sa.String(40), nullable=True),
        sa.Column("provider", sa.String(255), nullable=True),
        sa.Column("service_reference", sa.String(160), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_equipment_maintenance_revision"),
        sa.CheckConstraint("meter_value IS NULL OR meter_value >= 0", name="ck_equipment_maintenance_meter"),
        sa.ForeignKeyConstraint(["equipment_asset_id", "organization_id"], ["equipment_assets.id", "equipment_assets.organization_id"], name="fk_equipment_maintenance_asset_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_equipment_maintenance_project_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_equipment_maintenance"),
        sa.UniqueConstraint("id", "organization_id", name="uq_equipment_maintenance_id_org"),
    )
    op.create_index("ix_equipment_maintenance_org", "equipment_maintenance", ["organization_id"])
    op.create_index("ix_equipment_maintenance_asset", "equipment_maintenance", ["equipment_asset_id"])
    op.create_index("ix_equipment_maintenance_project", "equipment_maintenance", ["project_id"])
    op.create_index("ix_equipment_maintenance_asset_status", "equipment_maintenance", ["equipment_asset_id", "status", "due_date"])

    op.create_table(
        "materials",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("default_unit_code", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("active", "retired", name="materialstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_materials_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_materials_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_materials"),
        sa.UniqueConstraint("organization_id", "code", name="uq_materials_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_materials_id_org"),
    )
    op.create_index("ix_materials_org", "materials", ["organization_id"])
    op.create_index("ix_materials_code", "materials", ["code"])
    op.create_index("ix_materials_org_status", "materials", ["organization_id", "status"])

    op.create_table(
        "project_material_plans",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("unit_code", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("planned_quantity >= 0", name="ck_material_plans_quantity"),
        sa.CheckConstraint("revision >= 1", name="ck_material_plans_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_material_plans_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id", "organization_id"], ["materials.id", "materials.organization_id"], name="fk_material_plans_material_org", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_material_plans"),
        sa.UniqueConstraint("project_id", "material_id", name="uq_material_plans_project_material"),
        sa.UniqueConstraint("id", "organization_id", name="uq_material_plans_id_org"),
    )
    op.create_index("ix_material_plans_org", "project_material_plans", ["organization_id"])
    op.create_index("ix_material_plans_project", "project_material_plans", ["project_id"])
    op.create_index("ix_material_plans_material", "project_material_plans", ["material_id"])

    op.create_table(
        "material_deliveries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("unit_code", sa.String(40), nullable=False),
        sa.Column("supplier", sa.String(255), nullable=True),
        sa.Column("ticket_number", sa.String(160), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum("pending", "received", "rejected", "cancelled", name="materialdeliverystatus", native_enum=False), nullable=False, server_default="pending"),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_material_deliveries_quantity"),
        sa.CheckConstraint("revision >= 1", name="ck_material_deliveries_revision"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_material_deliveries_project_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id", "organization_id"], ["materials.id", "materials.organization_id"], name="fk_material_deliveries_material_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id", "received_by_membership_id", "organization_id"],
            ["project_memberships.project_id", "project_memberships.organization_membership_id", "project_memberships.organization_id"],
            name="fk_material_delivery_receiver_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_material_deliveries"),
        sa.UniqueConstraint("id", "organization_id", name="uq_material_deliveries_id_org"),
    )
    op.create_index("ix_material_deliveries_org", "material_deliveries", ["organization_id"])
    op.create_index("ix_material_deliveries_project", "material_deliveries", ["project_id"])
    op.create_index("ix_material_deliveries_material", "material_deliveries", ["material_id"])
    op.create_index("ix_material_deliveries_project_status", "material_deliveries", ["project_id", "status", "delivered_at"])

    permissions = sa.table(
        "permissions",
        sa.column("key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("risk", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "key": key,
                "module": "equipment" if key.startswith("equipment.") else "materials",
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
    permissions = sa.table("permissions", sa.column("key", sa.String()))
    op.execute(permissions.delete().where(permissions.c.key.in_([key for key, *_ in _PERMISSIONS])))
    op.drop_table("material_deliveries")
    op.drop_table("project_material_plans")
    op.drop_table("materials")
    op.drop_table("equipment_maintenance")
    op.drop_table("project_equipment_assignments")
    op.drop_table("equipment_assets")
