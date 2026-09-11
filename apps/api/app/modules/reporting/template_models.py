from datetime import datetime
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
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class TemplateVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class TemplateSourceKind(StrEnum):
    BUILTIN = "builtin"
    DESIGNER = "designer"
    UPLOADED = "uploaded"


class TemplateOutputFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"
    XLSX = "xlsx"
    DOCX = "docx"
    CSV = "csv"
    JSON = "json"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class ReportBrandingProfile(UUIDTimestampMixin, Base):
    __tablename__ = "report_branding_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_logo_asset_id", "company_logo_version", "organization_id"],
            [
                "file_versions.asset_id",
                "file_versions.version",
                "file_versions.organization_id",
            ],
            name="fk_report_branding_company_logo_version_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", name="uq_report_branding_profiles_org"),
        UniqueConstraint("id", "organization_id", name="uq_report_branding_profiles_id_org"),
        CheckConstraint("revision >= 1", name="ck_report_branding_profiles_revision"),
        CheckConstraint(
            "(company_logo_asset_id IS NULL AND company_logo_version IS NULL) OR "
            "(company_logo_asset_id IS NOT NULL AND company_logo_version IS NOT NULL)",
            name="ck_report_branding_profiles_logo_pair",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    company_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_logo_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    company_logo_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_header_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_footer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ReportTemplate(UUIDTimestampMixin, Base):
    __tablename__ = "report_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_report_templates_project_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_report_templates_id_org"),
        UniqueConstraint(
            "organization_id",
            "report_type_key",
            "project_id",
            "name",
            name="uq_report_templates_scope_name",
        ),
        CheckConstraint("current_version >= 0", name="ck_report_templates_current_version"),
        Index(
            "ix_report_templates_resolve",
            "organization_id",
            "report_type_key",
            "project_id",
            "is_default",
            "active",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_type_key: Mapped[str] = mapped_column(String(120), index=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ReportTemplateVersion(UUIDTimestampMixin, Base):
    __tablename__ = "report_template_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["report_templates.id", "report_templates.organization_id"],
            name="fk_report_template_versions_template_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_file_asset_id", "source_file_version", "organization_id"],
            [
                "file_versions.asset_id",
                "file_versions.version",
                "file_versions.organization_id",
            ],
            name="fk_report_template_versions_source_file_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("template_id", "version", name="uq_report_template_versions_version"),
        UniqueConstraint("id", "organization_id", name="uq_report_template_versions_id_org"),
        CheckConstraint("version >= 1", name="ck_report_template_versions_version"),
        CheckConstraint(
            "(source_file_asset_id IS NULL AND source_file_version IS NULL) OR "
            "(source_file_asset_id IS NOT NULL AND source_file_version IS NOT NULL)",
            name="ck_report_template_versions_source_pair",
        ),
        Index(
            "ix_report_template_versions_template_status",
            "template_id",
            "status",
            "version",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    template_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[TemplateVersionStatus] = mapped_column(
        Enum(TemplateVersionStatus, native_enum=False, values_callable=enum_values),
        default=TemplateVersionStatus.DRAFT,
    )
    source_kind: Mapped[TemplateSourceKind] = mapped_column(
        Enum(TemplateSourceKind, native_enum=False, values_callable=enum_values),
        default=TemplateSourceKind.DESIGNER,
    )
    source_file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_file_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_format: Mapped[str | None] = mapped_column(String(40), nullable=True)
    layout_spec: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provider_contract_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportRenderRecord(UUIDTimestampMixin, Base):
    __tablename__ = "report_render_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["projects.id", "projects.organization_id"],
            name="fk_report_render_records_project_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["template_version_id", "organization_id"],
            ["report_template_versions.id", "report_template_versions.organization_id"],
            name="fk_report_render_records_template_version_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["output_file_asset_id", "organization_id"],
            ["file_assets.id", "file_assets.organization_id"],
            name="fk_report_render_records_output_asset_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_report_render_records_id_org"),
        CheckConstraint("source_revision >= 1", name="ck_report_render_records_source_revision"),
        CheckConstraint("length(content_sha256) = 64", name="ck_report_render_records_sha256"),
        Index(
            "ix_report_render_records_source",
            "organization_id",
            "report_type_key",
            "source_entity_type",
            "source_entity_id",
            "created_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    report_type_key: Mapped[str] = mapped_column(String(120), index=True)
    source_entity_type: Mapped[str] = mapped_column(String(100))
    source_entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_revision: Mapped[int] = mapped_column(BigInteger)
    template_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    output_format: Mapped[TemplateOutputFormat] = mapped_column(
        Enum(TemplateOutputFormat, native_enum=False, values_callable=enum_values)
    )
    payload_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    presentation_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))
    output_file_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    generated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
