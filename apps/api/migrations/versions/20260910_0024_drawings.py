"""Add drawing engine structures.

Revision ID: 20260910_0024
Revises: 20260910_0023
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0024"
down_revision: str | None = "20260910_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("drawings.drawing.view", "drawings", "drawing", "view", "View drawing sets, sheets and published revisions within the authorized project scope.", "medium"),
    ("drawings.drawing.revise", "drawings", "drawing", "revise", "Create sheets and drawing revisions within the authorized project scope.", "high"),
    ("drawings.drawing.publish", "drawings", "drawing", "publish", "Publish or supersede controlled drawing revisions.", "high"),
    ("drawings.markup.manage", "drawings", "markup", "manage", "Create, update and retire drawing markups.", "medium"),
    ("drawings.measurement.manage", "drawings", "measurement", "manage", "Create calibrations and authoritative drawing measurements.", "medium"),
    ("drawings.comparison.run", "drawings", "comparison", "run", "Run drawing revision comparisons and overlays.", "medium"),
    ("drawings.drawing.manage", "drawings", "drawing", "manage", "Manage drawing sets, processing, archival and drawing configuration.", "high"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "drawing_sets",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("active", "archived", name="drawingsetstatus", native_enum=False), nullable=False, server_default="active"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_drawing_sets_version"),
        sa.ForeignKeyConstraint(["project_id", "organization_id"], ["projects.id", "projects.organization_id"], name="fk_drawing_sets_project_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_sets"),
        sa.UniqueConstraint("id", "organization_id", name="uq_drawing_sets_id_org"),
        sa.UniqueConstraint("project_id", "name", name="uq_drawing_sets_project_name"),
    )
    op.create_index("ix_drawing_sets_project_status", "drawing_sets", ["project_id", "status"], unique=False)
    op.create_index("ix_drawing_sets_organization_id", "drawing_sets", ["organization_id"], unique=False)

    op.create_table(
        "drawing_sheets",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_set_id", sa.Uuid(), nullable=False),
        sa.Column("sheet_number", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("discipline_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("current_revision_sequence", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_drawing_sheets_version"),
        sa.CheckConstraint("current_revision_sequence >= 0", name="ck_drawing_sheets_current_revision"),
        sa.ForeignKeyConstraint(["drawing_set_id", "organization_id"], ["drawing_sets.id", "drawing_sets.organization_id"], name="fk_drawing_sheets_set_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_sheets"),
        sa.UniqueConstraint("id", "organization_id", name="uq_drawing_sheets_id_org"),
        sa.UniqueConstraint("drawing_set_id", "sheet_number", name="uq_drawing_sheets_set_number"),
    )
    op.create_index("ix_drawing_sheets_set_discipline", "drawing_sheets", ["drawing_set_id", "discipline_code"], unique=False)
    op.create_index("ix_drawing_sheets_organization_id", "drawing_sheets", ["organization_id"], unique=False)

    op.create_table(
        "drawing_revisions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("sheet_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("revision_label", sa.String(length=80), nullable=False),
        sa.Column("file_version_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Enum("draft", "processing", "ready", "published", "superseded", "failed", name="drawingrevisionstatus", native_enum=False), nullable=False, server_default="draft"),
        sa.Column("render_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("renderer_key", sa.String(length=80), nullable=True),
        sa.Column("page_width", sa.Numeric(18, 6), nullable=True),
        sa.Column("page_height", sa.Numeric(18, 6), nullable=True),
        sa.Column("geometry_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("sequence >= 1", name="ck_drawing_revisions_sequence"),
        sa.CheckConstraint("source_page >= 1", name="ck_drawing_revisions_source_page"),
        sa.CheckConstraint("render_version >= 1", name="ck_drawing_revisions_render_version"),
        sa.ForeignKeyConstraint(["sheet_id", "organization_id"], ["drawing_sheets.id", "drawing_sheets.organization_id"], name="fk_drawing_revisions_sheet_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_version_id", "organization_id"], ["file_versions.id", "file_versions.organization_id"], name="fk_drawing_revisions_file_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_revision_id", "organization_id"], ["document_revisions.id", "document_revisions.organization_id"], name="fk_drawing_revisions_document_revision_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_drawing_revisions_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_revisions"),
        sa.UniqueConstraint("id", "organization_id", name="uq_drawing_revisions_id_org"),
        sa.UniqueConstraint("sheet_id", "sequence", name="uq_drawing_revisions_sheet_sequence"),
        sa.UniqueConstraint("sheet_id", "revision_label", name="uq_drawing_revisions_sheet_label"),
    )
    op.create_index("ix_drawing_revisions_sheet_status", "drawing_revisions", ["sheet_id", "status"], unique=False)
    op.create_index("ix_drawing_revisions_organization_id", "drawing_revisions", ["organization_id"], unique=False)

    op.create_table(
        "drawing_render_packages",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("render_version", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("render_version >= 1", name="ck_drawing_render_packages_version"),
        sa.ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_render_packages_revision_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_render_packages"),
        sa.UniqueConstraint("drawing_revision_id", "render_version", name="uq_drawing_render_packages_revision_version"),
    )

    op.create_table(
        "drawing_calibrations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("point_a_x", sa.Numeric(18, 8), nullable=False),
        sa.Column("point_a_y", sa.Numeric(18, 8), nullable=False),
        sa.Column("point_b_x", sa.Numeric(18, 8), nullable=False),
        sa.Column("point_b_y", sa.Numeric(18, 8), nullable=False),
        sa.Column("real_length", sa.Numeric(24, 8), nullable=False),
        sa.Column("unit_code", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_drawing_calibrations_version"),
        sa.CheckConstraint("real_length > 0", name="ck_drawing_calibrations_real_length"),
        sa.ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_calibrations_revision_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_drawing_calibrations_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_calibrations"),
        sa.UniqueConstraint("id", "organization_id", name="uq_drawing_calibrations_id_org"),
        sa.UniqueConstraint("drawing_revision_id", "version", name="uq_drawing_calibrations_revision_version"),
    )

    op.create_table(
        "drawing_markups",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("markup_type", sa.Enum("text", "arrow", "cloud", "polyline", "rectangle", "freehand", name="drawingmarkuptype", native_enum=False), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("style", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_drawing_markups_version"),
        sa.ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_markups_revision_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_drawing_markups_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_markups"),
        sa.UniqueConstraint("id", "organization_id", name="uq_drawing_markups_id_org"),
    )
    op.create_index("ix_drawing_markups_revision_type", "drawing_markups", ["drawing_revision_id", "markup_type"], unique=False)

    op.create_table(
        "drawing_measurements",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("calibration_id", sa.Uuid(), nullable=True),
        sa.Column("measurement_type", sa.Enum("length", "area", "volume", "count", name="drawingmeasurementtype", native_enum=False), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("value", sa.Numeric(28, 10), nullable=False),
        sa.Column("unit_code", sa.String(length=32), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("value >= 0", name="ck_drawing_measurements_value"),
        sa.CheckConstraint("version >= 1", name="ck_drawing_measurements_version"),
        sa.ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_measurements_revision_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["calibration_id", "organization_id"], ["drawing_calibrations.id", "drawing_calibrations.organization_id"], name="fk_drawing_measurements_calibration_org", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_drawing_measurements_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_measurements"),
    )
    op.create_index("ix_drawing_measurements_revision_type", "drawing_measurements", ["drawing_revision_id", "measurement_type"], unique=False)

    op.create_table(
        "drawing_pins",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("pin_type", sa.Enum("rfi", "photo", "punch", "inspection", "submittal", "custom", name="drawingpintype", native_enum=False), nullable=False),
        sa.Column("target_entity_type", sa.String(length=100), nullable=False),
        sa.Column("target_entity_id", sa.String(length=160), nullable=False),
        sa.Column("x", sa.Numeric(12, 10), nullable=False),
        sa.Column("y", sa.Numeric(12, 10), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("x >= 0 AND x <= 1", name="ck_drawing_pins_x"),
        sa.CheckConstraint("y >= 0 AND y <= 1", name="ck_drawing_pins_y"),
        sa.CheckConstraint("version >= 1", name="ck_drawing_pins_version"),
        sa.ForeignKeyConstraint(["drawing_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_pins_revision_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_drawing_pins_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_pins"),
    )
    op.create_index("ix_drawing_pins_revision_type", "drawing_pins", ["drawing_revision_id", "pin_type"], unique=False)

    op.create_table(
        "drawing_comparisons",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision_id", sa.Uuid(), nullable=False),
        sa.Column("compare_revision_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum("queued", "processing", "ready", "failed", name="drawingcomparisonstatus", native_enum=False), nullable=False, server_default="queued"),
        sa.Column("alignment", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("result_manifest", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("base_revision_id <> compare_revision_id", name="ck_drawing_comparisons_distinct"),
        sa.ForeignKeyConstraint(["base_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_comparisons_base_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compare_revision_id", "organization_id"], ["drawing_revisions.id", "drawing_revisions.organization_id"], name="fk_drawing_comparisons_compare_org", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_drawing_comparisons"),
        sa.UniqueConstraint("base_revision_id", "compare_revision_id", name="uq_drawing_comparisons_pair"),
    )
    op.create_index("ix_drawing_comparisons_org_status", "drawing_comparisons", ["organization_id", "status"], unique=False)

    permissions = sa.table("permissions", sa.column("key", sa.String()), sa.column("module", sa.String()), sa.column("resource", sa.String()), sa.column("action", sa.String()), sa.column("description", sa.Text()), sa.column("risk", sa.String()), sa.column("is_active", sa.Boolean()))
    op.bulk_insert(permissions, [{"key": key, "module": module, "resource": resource, "action": action, "description": description, "risk": risk, "is_active": True} for key, module, resource, action, description, risk in _PERMISSIONS])


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in _PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ({keys})")
    op.drop_table("drawing_comparisons")
    op.drop_table("drawing_pins")
    op.drop_table("drawing_measurements")
    op.drop_table("drawing_markups")
    op.drop_table("drawing_calibrations")
    op.drop_table("drawing_render_packages")
    op.drop_table("drawing_revisions")
    op.drop_table("drawing_sheets")
    op.drop_table("drawing_sets")
