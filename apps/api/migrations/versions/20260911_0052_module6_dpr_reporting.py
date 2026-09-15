"""Add structured DPR reporting and reusable report templates.

Revision ID: 20260911_0052
Revises: 20260911_0051
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0052"
down_revision: str | None = "20260911_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DPR_PERMISSIONS = (
    (
        "field.dpr.template.view",
        "dpr_template",
        "view",
        "View effective DPR report templates, layout contracts and branding.",
        "medium",
    ),
    (
        "field.dpr.template.manage",
        "dpr_template",
        "manage",
        "Create, version and publish DPR report templates and company branding.",
        "high",
    ),
    (
        "field.dpr.render",
        "dpr_report",
        "render",
        "Generate permission-scoped DPR print and export outputs.",
        "high",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_daily_reports_scope",
        "daily_reports",
        ["id", "project_id", "organization_id"],
    )

    op.create_table(
        "dpr_work_progress_entries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("daily_report_id", sa.Uuid(), nullable=False),
        sa.Column("wbs_code_id", sa.Uuid(), nullable=True),
        sa.Column("boq_item_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=True),
        sa.Column("unit_code", sa.String(length=40), nullable=True),
        sa.Column("progress_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum(
                "manual",
                "measurement",
                "schedule",
                "integration",
                name="dprworkprogresssourcetype",
                native_enum=False,
            ),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_revision", sa.BigInteger(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_dpr_work_progress_quantity"),
        sa.CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="ck_dpr_work_progress_percent",
        ),
        sa.CheckConstraint(
            "wbs_code_id IS NOT NULL OR boq_item_id IS NOT NULL",
            name="ck_dpr_work_progress_control_reference",
        ),
        sa.CheckConstraint(
            "source_revision IS NULL OR source_revision >= 1",
            name="ck_dpr_work_progress_source_revision",
        ),
        sa.ForeignKeyConstraint(
            ["daily_report_id", "project_id", "organization_id"],
            ["daily_reports.id", "daily_reports.project_id", "daily_reports.organization_id"],
            name="fk_dpr_work_progress_report_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_dpr_work_progress_wbs_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_dpr_work_progress_boq_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dpr_work_progress_entries"),
        sa.UniqueConstraint("id", "organization_id", name="uq_dpr_work_progress_id_org"),
    )
    op.create_index("ix_dpr_work_progress_report", "dpr_work_progress_entries", ["daily_report_id", "created_at"])
    op.create_index("ix_dpr_work_progress_project_wbs", "dpr_work_progress_entries", ["project_id", "wbs_code_id"])
    op.create_index("ix_dpr_work_progress_project_boq", "dpr_work_progress_entries", ["project_id", "boq_item_id"])
    op.create_index("ix_dpr_work_progress_entries_organization_id", "dpr_work_progress_entries", ["organization_id"])

    op.create_table(
        "report_branding_profiles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("company_display_name", sa.String(length=255), nullable=True),
        sa.Column("company_logo_asset_id", sa.Uuid(), nullable=True),
        sa.Column("company_logo_version", sa.Integer(), nullable=True),
        sa.Column("default_header_text", sa.String(length=500), nullable=True),
        sa.Column("default_footer_text", sa.String(length=500), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("revision >= 1", name="ck_report_branding_profiles_revision"),
        sa.CheckConstraint(
            "(company_logo_asset_id IS NULL AND company_logo_version IS NULL) OR "
            "(company_logo_asset_id IS NOT NULL AND company_logo_version IS NOT NULL)",
            name="ck_report_branding_profiles_logo_pair",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_logo_asset_id", "company_logo_version", "organization_id"],
            ["file_versions.asset_id", "file_versions.version", "file_versions.organization_id"],
            name="fk_report_branding_company_logo_version_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_report_branding_profiles"),
        sa.UniqueConstraint("organization_id", name="uq_report_branding_profiles_org"),
        sa.UniqueConstraint("id", "organization_id", name="uq_report_branding_profiles_id_org"),
    )
    op.create_index("ix_report_branding_profiles_organization_id", "report_branding_profiles", ["organization_id"])

    op.create_table(
        "report_templates",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("report_type_key", sa.String(length=120), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("current_version >= 0", name="ck_report_templates_current_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_report_templates_project_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_report_templates"),
        sa.UniqueConstraint("id", "organization_id", name="uq_report_templates_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "report_type_key",
            "project_id",
            "name",
            name="uq_report_templates_scope_name",
        ),
    )
    op.create_index("ix_report_templates_organization_id", "report_templates", ["organization_id"])
    op.create_index("ix_report_templates_report_type_key", "report_templates", ["report_type_key"])
    op.create_index("ix_report_templates_project_id", "report_templates", ["project_id"])
    op.create_index(
        "ix_report_templates_resolve",
        "report_templates",
        ["organization_id", "report_type_key", "project_id", "is_default", "active"],
    )

    op.create_table(
        "report_template_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "retired", name="templateversionstatus", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "source_kind",
            sa.Enum("builtin", "designer", "uploaded", name="templatesourcekind", native_enum=False),
            nullable=False,
            server_default="designer",
        ),
        sa.Column("source_file_asset_id", sa.Uuid(), nullable=True),
        sa.Column("source_file_version", sa.Integer(), nullable=True),
        sa.Column("source_format", sa.String(length=40), nullable=True),
        sa.Column("layout_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider_contract_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("version >= 1", name="ck_report_template_versions_version"),
        sa.CheckConstraint(
            "(source_file_asset_id IS NULL AND source_file_version IS NULL) OR "
            "(source_file_asset_id IS NOT NULL AND source_file_version IS NOT NULL)",
            name="ck_report_template_versions_source_pair",
        ),
        sa.ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["report_templates.id", "report_templates.organization_id"],
            name="fk_report_template_versions_template_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_asset_id", "source_file_version", "organization_id"],
            ["file_versions.asset_id", "file_versions.version", "file_versions.organization_id"],
            name="fk_report_template_versions_source_file_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_report_template_versions"),
        sa.UniqueConstraint("template_id", "version", name="uq_report_template_versions_version"),
        sa.UniqueConstraint("id", "organization_id", name="uq_report_template_versions_id_org"),
    )
    op.create_index("ix_report_template_versions_template_id", "report_template_versions", ["template_id"])
    op.create_index("ix_report_template_versions_organization_id", "report_template_versions", ["organization_id"])
    op.create_index(
        "ix_report_template_versions_template_status",
        "report_template_versions",
        ["template_id", "status", "version"],
    )

    op.create_table(
        "report_render_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("report_type_key", sa.String(length=120), nullable=False),
        sa.Column("source_entity_type", sa.String(length=100), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_revision", sa.BigInteger(), nullable=False),
        sa.Column("template_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "output_format",
            sa.Enum("pdf", "html", "xlsx", "docx", "csv", "json", name="templateoutputformat", native_enum=False),
            nullable=False,
        ),
        sa.Column("payload_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("presentation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_file_asset_id", sa.Uuid(), nullable=True),
        sa.Column("generated_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("source_revision >= 1", name="ck_report_render_records_source_revision"),
        sa.CheckConstraint("length(content_sha256) = 64", name="ck_report_render_records_sha256"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_report_render_records_project_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id", "organization_id"],
            ["report_template_versions.id", "report_template_versions.organization_id"],
            name="fk_report_render_records_template_version_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["output_file_asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_report_render_records_output_asset_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_report_render_records"),
        sa.UniqueConstraint("id", "organization_id", name="uq_report_render_records_id_org"),
    )
    op.create_index("ix_report_render_records_organization_id", "report_render_records", ["organization_id"])
    op.create_index("ix_report_render_records_project_id", "report_render_records", ["project_id"])
    op.create_index("ix_report_render_records_report_type_key", "report_render_records", ["report_type_key"])
    op.create_index("ix_report_render_records_source_entity_id", "report_render_records", ["source_entity_id"])
    op.create_index("ix_report_render_records_template_version_id", "report_render_records", ["template_version_id"])
    op.create_index(
        "ix_report_render_records_source",
        "report_render_records",
        ["organization_id", "report_type_key", "source_entity_type", "source_entity_id", "created_at"],
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
                "module": "field",
                "resource": resource,
                "action": action,
                "description": description,
                "risk": risk,
                "is_active": True,
            }
            for key, resource, action, description, risk in _DPR_PERMISSIONS
        ],
    )

    permission_keys = [key for key, *_ in _DPR_PERMISSIONS]
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_key)
            SELECT roles.id, permissions.key
            FROM roles
            CROSS JOIN permissions
            WHERE roles.organization_id IS NOT NULL
              AND roles.key = 'company-admin'
              AND roles.is_protected IS TRUE
              AND roles.is_active IS TRUE
              AND permissions.key = ANY(:permission_keys)
              AND permissions.is_active IS TRUE
            ON CONFLICT DO NOTHING
            """
        ).bindparams(permission_keys=permission_keys)
    )
    op.execute(
        sa.text(
            """
            UPDATE organization_authorization_state AS state
            SET revision = state.revision + 1,
                updated_at = now()
            WHERE EXISTS (
                SELECT 1 FROM roles
                WHERE roles.organization_id = state.organization_id
                  AND roles.key = 'company-admin'
                  AND roles.is_protected IS TRUE
                  AND roles.is_active IS TRUE
            )
            """
        )
    )


def downgrade() -> None:
    permission_keys = [key for key, *_ in _DPR_PERMISSIONS]
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions AS role_permission
            USING roles
            WHERE role_permission.role_id = roles.id
              AND roles.organization_id IS NOT NULL
              AND roles.key = 'company-admin'
              AND roles.is_protected IS TRUE
              AND role_permission.permission_key = ANY(:permission_keys)
            """
        ).bindparams(permission_keys=permission_keys)
    )
    op.execute(sa.text("DELETE FROM permissions WHERE key = ANY(:keys)").bindparams(keys=permission_keys))
    op.drop_table("report_render_records")
    op.drop_table("report_template_versions")
    op.drop_table("report_templates")
    op.drop_table("report_branding_profiles")
    op.drop_table("dpr_work_progress_entries")
    op.drop_constraint("uq_daily_reports_scope", "daily_reports", type_="unique")
