"""Align new-company database defaults with the India product preset.

Revision ID: 20260911_0048
Revises: 20260911_0047
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0048"
down_revision: str | None = "20260911_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "organization_settings",
        "locale",
        existing_type=sa.String(length=35),
        existing_nullable=False,
        server_default="en-IN",
    )
    op.alter_column(
        "organization_settings",
        "timezone",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        server_default="Asia/Kolkata",
    )
    op.alter_column(
        "organization_settings",
        "base_currency",
        existing_type=sa.String(length=3),
        existing_nullable=False,
        server_default="INR",
    )


def downgrade() -> None:
    op.alter_column(
        "organization_settings",
        "base_currency",
        existing_type=sa.String(length=3),
        existing_nullable=False,
        server_default="USD",
    )
    op.alter_column(
        "organization_settings",
        "timezone",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        server_default="UTC",
    )
    op.alter_column(
        "organization_settings",
        "locale",
        existing_type=sa.String(length=35),
        existing_nullable=False,
        server_default="en-US",
    )
