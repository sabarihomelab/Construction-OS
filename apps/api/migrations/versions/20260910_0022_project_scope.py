"""Add project lifecycle, memberships and project-scoped roles.

Revision ID: 20260910_0022
Revises: 20260910_0021
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0022"
down_revision: str | None = "20260910_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROJECT_PERMISSIONS = (
    ("projects.project.create", "projects", "project", "create", "Create projects for the company.", "high"),
    ("projects.project.update", "projects", "project", "update", "Update project details within the authorized scope.", "high"),
    ("projects.project.archive", "projects", "project", "archive", "Move projects into closeout, complete, or archived states within the authorized scope.", "high"),
    ("projects.membership.view", "projects", "membership", "view", "View project team memberships within the authorized scope.", "medium"),
    ("projects.membership.manage", "projects", "membership", "manage", "Add, suspend, end, and assign roles to project memberships.", "critical"),
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_organization_memberships_id_org",
        "organization_memberships",
        ["id", "organization_id"],
    )
    op.create_unique_constraint("uq_roles_id_org", "roles", ["id", "organization_id"])

    op.create_table(
        "projects",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "planning",
                "active",
                "on_hold",
                "closeout",
                "complete",
                "archived",
                name="projectstatus",
                native_enum=False,
            ),
            nullable=False,
            server_default="planning",
        ),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.Column("unit_system", sa.String(length=16), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_completion_date", sa.Date(), nullable=True),
        sa.Column("address_line_1", sa.String(length=255), nullable=True),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("locality", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("revision >= 1", name="ck_projects_revision"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_projects_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("organization_id", "number", name="uq_projects_org_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_projects_id_org"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"], unique=False)
    op.create_index("ix_projects_number", "projects", ["number"], unique=False)
    op.create_index("ix_projects_org_status", "projects", ["organization_id", "status"], unique=False)

    op.create_table(
        "project_memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_membership_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", "ended", name="projectmembershipstatus", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_project_memberships_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_project_memberships_org_membership_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_memberships"),
        sa.UniqueConstraint(
            "project_id",
            "organization_membership_id",
            name="uq_project_memberships_project_membership",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_project_memberships_id_org"),
    )
    op.create_index("ix_project_memberships_organization_id", "project_memberships", ["organization_id"], unique=False)
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"], unique=False)
    op.create_index("ix_project_memberships_organization_membership_id", "project_memberships", ["organization_membership_id"], unique=False)
    op.create_index("ix_project_memberships_org_status", "project_memberships", ["organization_id", "status"], unique=False)

    op.create_table(
        "project_role_assignments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_membership_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["project_membership_id", "organization_id"],
            ["project_memberships.id", "project_memberships.organization_id"],
            name="fk_project_role_assignments_membership_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id", "organization_id"],
            ["roles.id", "roles.organization_id"],
            name="fk_project_role_assignments_role_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_role_assignments"),
        sa.UniqueConstraint(
            "project_membership_id",
            "role_id",
            name="uq_project_role_assignments_membership_role",
        ),
    )
    op.create_index("ix_project_role_assignments_organization_id", "project_role_assignments", ["organization_id"], unique=False)
    op.create_index("ix_project_role_assignments_project_membership_id", "project_role_assignments", ["project_membership_id"], unique=False)
    op.create_index("ix_project_role_assignments_role_id", "project_role_assignments", ["role_id"], unique=False)

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
                "module": module,
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, module, resource, action, description, risk in _PROJECT_PERMISSIONS
        ],
    )


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in _PROJECT_PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")
    op.drop_table("project_role_assignments")
    op.drop_table("project_memberships")
    op.drop_table("projects")
    op.drop_constraint("uq_roles_id_org", "roles", type_="unique")
    op.drop_constraint("uq_organization_memberships_id_org", "organization_memberships", type_="unique")
