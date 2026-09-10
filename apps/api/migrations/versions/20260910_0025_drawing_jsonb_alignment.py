"""Align drawing metadata storage to PostgreSQL JSONB.

Revision ID: 20260910_0025
Revises: 20260910_0024
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0025"
down_revision: str | None = "20260910_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("drawing_revisions", "geometry_metadata"),
    ("drawing_render_packages", "manifest"),
    ("drawing_markups", "geometry"),
    ("drawing_markups", "style"),
    ("drawing_measurements", "geometry"),
    ("drawing_comparisons", "alignment"),
    ("drawing_comparisons", "result_manifest"),
)


def upgrade() -> None:
    for table_name, column_name in _COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            type_=postgresql.JSONB(astext_type=postgresql.TEXT()),
            postgresql_using=f"{column_name}::jsonb",
        )


def downgrade() -> None:
    for table_name, column_name in reversed(_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            type_=postgresql.JSON(astext_type=postgresql.TEXT()),
            postgresql_using=f"{column_name}::json",
        )
