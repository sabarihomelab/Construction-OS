"""Enforce RFI responsibility against project membership.

Revision ID: 20260910_0027
Revises: 20260910_0026
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260910_0027"
down_revision: str | None = "20260910_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_project_memberships_project_member_org",
        "project_memberships",
        ["project_id", "organization_membership_id", "organization_id"],
    )
    op.drop_constraint(
        "fk_rfis_ball_in_court_membership_org",
        "rfis",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_rfis_ball_in_court_project_member_org",
        "rfis",
        "project_memberships",
        ["project_id", "ball_in_court_membership_id", "organization_id"],
        ["project_id", "organization_membership_id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_rfis_ball_in_court_project_member_org",
        "rfis",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_rfis_ball_in_court_membership_org",
        "rfis",
        "organization_memberships",
        ["ball_in_court_membership_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "uq_project_memberships_project_member_org",
        "project_memberships",
        type_="unique",
    )
