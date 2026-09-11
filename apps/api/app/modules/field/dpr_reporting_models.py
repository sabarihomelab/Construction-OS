from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class DPRTemplateVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class DPRTemplateSourceKind(StrEnum):
    BUILTIN = "builtin"
    DESIGNER = "designer"
    UPLOADED = "uploaded"


class DPROutputFormat(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"
    DOCX = "docx"
    CSV = "csv"
    HTML = "html"
    JSON = "json"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class DPRBrandingProfile(UUIDTimestampMixin, Base):
    __tablename__ = "dpr_branding_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["logo_asset_id", "logo_version", "organization_id"],
            [
                "file_versions.asset_id",
                "file_versions.version",
                "file_versions.organization_id",
            ],
            name="fk_dpr_branding_logo_version_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", name="uq_dpr_branding_org"),
        UniqueConstraint("id", "organization_id", name="uq_dpr_branding_id_org"),
        CheckConstraint("revision >= 1", name="ck_dpr_branding_revision"),
        CheckConstraint(
            "(logo_asset_id IS NULL AND logo_version IS NULL) OR "
            "(logo_asset_id IS NOT NULL AND logo_version IS NOT NULL)",
            name="ck_dpr_branding_logo_pair",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    logo_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    header_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DPRTemplate(UUIDTimestampMixin, Base):
    __tablename__ = "dpr_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_dpr_templates_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_dpr_templates_id_org"),
        CheckConstraint("current_version >= 0", name="ck_dpr_templates_current_version"),
        Index("ix_dpr_templates_org_project", "organization_id", "project_id", "active"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DPRTemplateVersion(UUIDTimestampMixin, Base):
    __tablename__ = "dpr_template_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["dpr_templates.id", "dpr_templates.organization_id"],
            name="fk_dpr_template_versions_template_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_file_asset_id", "source_file_version", "organization_id"],
            [
                "file_versions.asset_id",
                "file_versions.version",
                "file_versions.organization_id",
            ],
            name="fk_dpr_template_versions_source_file_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("template_id", "version", name="uq_dpr_template_versions_version"),
        UniqueConstraint("id", "organization_id", name="uq_dpr_template_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_dpr_template_versions_version"),
        CheckConstraint(
            "(source_file_asset_id IS NULL AND source_file_version IS NULL) OR "
            "(source_file_asset_id IS NOT NULL AND source_file_version IS NOT NULL)",
            name="ck_dpr_template_versions_source_pair",
        ),
        Index("ix_dpr_template_versions_template_status", "template_id", "status", "version"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    template_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[DPRTemplateVersionStatus] = mapped_column(
        Enum(DPRTemplateVersionStatus, native_enum=False, values_callable=enum_values),
        default=DPRTemplateVersionStatus.DRAFT,
    )
    source_kind: Mapped[DPRTemplateSourceKind] = mapped_column(
        Enum(DPRTemplateSourceKind, native_enum=False, values_callable=enum_values),
        default=DPRTemplateSourceKind.DESIGNER,
    )
    source_file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_file_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_format: Mapped[str | None] = mapped_column(String(40), nullable=True)
    layout_spec: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyReportMaterialEntry(UUIDTimestampMixin, Base):
    __tablename__ = "daily_report_material_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_daily_report_material_report_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_daily_report_material_project_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["material_id", "organization_id"],
            ["materials.id", "materials.organization_id"],
            name="fk_daily_report_material_material_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["wbs_code_id", "project_id", "organization_id"],
            ["project_wbs_codes.id", "project_wbs_codes.project_id", "project_wbs_codes.organization_id"],
            name="fk_daily_report_material_wbs_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["boq_item_id", "project_id", "organization_id"],
            ["project_boq_items.id", "project_boq_items.project_id", "project_boq_items.organization_id"],
            name="fk_daily_report_material_boq_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_daily_report_material_id_org"),
        CheckConstraint("quantity > 0", name="ck_daily_report_material_quantity"),
        Index("ix_daily_report_material_report", "daily_report_id"),
        Index("ix_daily_report_material_project_wbs", "project_id", "wbs_code_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    material_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    material_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_code: Mapped[str] = mapped_column(String(40))
    wbs_code_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    boq_item_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DPRSourceLink(UUIDTimestampMixin, Base):
    __tablename__ = "dpr_source_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_dpr_source_links_report_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "daily_report_id",
            "section_name",
            "source_type",
            "source_id",
            name="uq_dpr_source_links_report_source",
        ),
        Index("ix_dpr_source_links_entry", "entry_type", "entry_id"),
        Index("ix_dpr_source_links_report", "daily_report_id", "section_name"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    section_name: Mapped[str] = mapped_column(String(40))
    entry_type: Mapped[str] = mapped_column(String(80))
    entry_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_type: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[str] = mapped_column(String(160))
    source_revision: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class DPRRenderRecord(UUIDTimestampMixin, Base):
    __tablename__ = "dpr_render_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_report_id", "organization_id"],
            ["daily_reports.id", "daily_reports.organization_id"],
            name="fk_dpr_render_records_report_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_dpr_render_records_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["template_version_id", "organization_id"],
            ["dpr_template_versions.id", "dpr_template_versions.organization_id"],
            name="fk_dpr_render_records_template_version_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["output_file_asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_dpr_render_records_output_asset_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_dpr_render_records_id_org"),
        CheckConstraint("report_revision >= 1", name="ck_dpr_render_records_report_revision"),
        CheckConstraint("length(content_sha256) = 64", name="ck_dpr_render_records_sha256"),
        Index("ix_dpr_render_records_report", "daily_report_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    daily_report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    report_revision: Mapped[int] = mapped_column(BigInteger)
    template_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    output_format: Mapped[DPROutputFormat] = mapped_column(
        Enum(DPROutputFormat, native_enum=False, values_callable=enum_values)
    )
    data_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    presentation_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))
    output_file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    generated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
