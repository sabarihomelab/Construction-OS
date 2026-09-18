"""Persist exact issued report file versions and issuance metadata.

Revision ID: 20260911_0053
Revises: 20260911_0052
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0053"
down_revision: str | None = "20260911_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "report_render_records",
        sa.Column("generation_trigger", sa.String(length=40), nullable=False, server_default="manual"),
    )
    op.add_column(
        "report_render_records",
        sa.Column("output_filename", sa.String(length=255), nullable=False, server_default="report.pdf"),
    )
    op.add_column(
        "report_render_records",
        sa.Column("output_file_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "report_render_records",
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(
        "fk_report_render_records_output_asset_org",
        "report_render_records",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_report_render_records_output_file_version_org",
        "report_render_records",
        "file_versions",
        ["output_file_asset_id", "output_file_version", "organization_id"],
        ["asset_id", "version", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_report_render_records_output_file_pair",
        "report_render_records",
        "(output_file_asset_id IS NULL AND output_file_version IS NULL) OR "
        "(output_file_asset_id IS NOT NULL AND output_file_version IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_report_render_records_output_file_pair",
        "report_render_records",
        type_="check",
    )
    op.drop_constraint(
        "fk_report_render_records_output_file_version_org",
        "report_render_records",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_report_render_records_output_asset_org",
        "report_render_records",
        "file_assets",
        ["output_file_asset_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.drop_column("report_render_records", "issued_at")
    op.drop_column("report_render_records", "output_file_version")
    op.drop_column("report_render_records", "output_filename")
    op.drop_column("report_render_records", "generation_trigger")
