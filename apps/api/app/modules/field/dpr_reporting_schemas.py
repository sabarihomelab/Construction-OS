from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.field.dpr_reporting_models import (
    DPROutputFormat,
    DPRTemplateSourceKind,
    DPRTemplateVersionStatus,
)


class DPRPageSize(StrEnum):
    A4 = "a4"
    A3 = "a3"
    LETTER = "letter"


class DPRPageOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class DPRCompanyNameMode(StrEnum):
    ORGANIZATION = "organization"
    LEGAL = "legal"
    CUSTOM = "custom"


class DPRLayoutElementKind(StrEnum):
    PROJECT_SUMMARY = "project_summary"
    WEATHER = "weather"
    CREW = "crew"
    WORK = "work"
    MATERIALS = "materials"
    EQUIPMENT = "equipment"
    DELIVERIES = "deliveries"
    PRODUCTION = "production"
    DELAYS = "delays"
    SAFETY = "safety"
    PHOTOS = "photos"
    NOTES = "notes"
    SIGNATURES = "signatures"
    CUSTOM_TEXT = "custom_text"
    PAGE_BREAK = "page_break"


class DPRPageSpec(BaseModel):
    size: DPRPageSize = DPRPageSize.A4
    orientation: DPRPageOrientation = DPRPageOrientation.PORTRAIT
    margin_top_mm: int = Field(default=12, ge=0, le=50)
    margin_right_mm: int = Field(default=12, ge=0, le=50)
    margin_bottom_mm: int = Field(default=12, ge=0, le=50)
    margin_left_mm: int = Field(default=12, ge=0, le=50)
    model_config = ConfigDict(extra="forbid")


class DPRBrandingSpec(BaseModel):
    company_name_mode: DPRCompanyNameMode = DPRCompanyNameMode.ORGANIZATION
    custom_company_name: str | None = Field(default=None, max_length=255)
    logo_asset_id: UUID | None = None
    logo_version: int | None = Field(default=None, ge=1)
    report_title: str = Field(default="Daily Progress Report", min_length=1, max_length=180)
    show_project_number: bool = True
    show_project_name: bool = True
    show_project_address: bool = True
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_branding(self) -> "DPRBrandingSpec":
        if self.company_name_mode == DPRCompanyNameMode.CUSTOM and not (
            self.custom_company_name and self.custom_company_name.strip()
        ):
            raise ValueError("custom_company_name is required when company_name_mode is custom")
        if (self.logo_asset_id is None) != (self.logo_version is None):
            raise ValueError("logo_asset_id and logo_version must be supplied together")
        return self


class DPRHeaderFooterSpec(BaseModel):
    header_left: str | None = Field(default=None, max_length=500)
    header_center: str | None = Field(default=None, max_length=500)
    header_right: str | None = Field(default=None, max_length=500)
    footer_left: str | None = Field(default=None, max_length=500)
    footer_center: str | None = Field(default=None, max_length=500)
    footer_right: str | None = Field(default=None, max_length=500)
    show_page_number: bool = True
    show_generated_timestamp: bool = False
    model_config = ConfigDict(extra="forbid")


class DPRLayoutElement(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    kind: DPRLayoutElementKind
    order: int = Field(ge=0, le=10000)
    column_span: int = Field(default=12, ge=1, le=12)
    visible: bool = True
    start_new_page: bool = False
    title: str | None = Field(default=None, max_length=180)
    fields: list[str] = Field(default_factory=list, max_length=50)
    custom_text: str | None = None
    style: dict[str, object] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_element(self) -> "DPRLayoutElement":
        if self.kind == DPRLayoutElementKind.CUSTOM_TEXT and not (
            self.custom_text and self.custom_text.strip()
        ):
            raise ValueError("custom_text is required for custom_text elements")
        if self.kind == DPRLayoutElementKind.PAGE_BREAK:
            self.column_span = 12
        return self


class DPRLayoutSpec(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    page: DPRPageSpec = Field(default_factory=DPRPageSpec)
    branding: DPRBrandingSpec = Field(default_factory=DPRBrandingSpec)
    header_footer: DPRHeaderFooterSpec = Field(default_factory=DPRHeaderFooterSpec)
    elements: list[DPRLayoutElement]
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_elements(self) -> "DPRLayoutSpec":
        ids = [item.id for item in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("DPR layout element ids must be unique")
        if not any(item.visible and item.kind != DPRLayoutElementKind.PAGE_BREAK for item in self.elements):
            raise ValueError("DPR layout must contain at least one visible content element")
        return self


class DPRBrandingUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    display_name: str | None = Field(default=None, max_length=255)
    logo_asset_id: UUID | None = None
    logo_version: int | None = Field(default=None, ge=1)
    header_text: str | None = Field(default=None, max_length=500)
    footer_text: str | None = Field(default=None, max_length=500)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_logo_pair(self) -> "DPRBrandingUpdate":
        if (self.logo_asset_id is None) != (self.logo_version is None):
            raise ValueError("logo_asset_id and logo_version must be supplied together")
        return self


class DPRBrandingRead(BaseModel):
    id: UUID
    organization_id: UUID
    display_name: str | None
    logo_asset_id: UUID | None
    logo_version: int | None
    header_text: str | None
    footer_text: str | None
    revision: int
    updated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DPRTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    company_wide: bool = False
    is_default: bool = False
    model_config = ConfigDict(extra="forbid")


class DPRTemplateRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    name: str
    description: str | None
    active: bool
    is_default: bool
    current_version: int
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DPRTemplateVersionCreate(BaseModel):
    source_kind: DPRTemplateSourceKind = DPRTemplateSourceKind.DESIGNER
    source_file_asset_id: UUID | None = None
    source_file_version: int | None = Field(default=None, ge=1)
    source_format: str | None = Field(default=None, max_length=40)
    layout: DPRLayoutSpec
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_source(self) -> "DPRTemplateVersionCreate":
        paired = self.source_file_asset_id is not None and self.source_file_version is not None
        if (self.source_file_asset_id is None) != (self.source_file_version is None):
            raise ValueError("source_file_asset_id and source_file_version must be supplied together")
        if self.source_kind == DPRTemplateSourceKind.UPLOADED and not paired:
            raise ValueError("Uploaded DPR templates must pin a File Asset and version")
        if self.source_kind == DPRTemplateSourceKind.UPLOADED and not self.source_format:
            raise ValueError("source_format is required for uploaded DPR templates")
        return self


class DPRTemplateVersionRead(BaseModel):
    id: UUID
    organization_id: UUID
    template_id: UUID
    version: int
    status: DPRTemplateVersionStatus
    source_kind: DPRTemplateSourceKind
    source_file_asset_id: UUID | None
    source_file_version: int | None
    source_format: str | None
    layout_spec: dict[str, object]
    created_by_user_id: UUID | None
    published_by_user_id: UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DPRTemplatePublish(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid")


class DPRRenderRequest(BaseModel):
    output_format: DPROutputFormat
    template_version_id: UUID | None = None
    record_generation: bool = True
    model_config = ConfigDict(extra="forbid")


class DPRRenderPreview(BaseModel):
    report_id: UUID
    report_revision: int
    template_version_id: UUID
    data_snapshot: dict[str, object]
    presentation_snapshot: dict[str, object]


class DPRRenderRecordRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    daily_report_id: UUID
    report_revision: int
    template_version_id: UUID
    output_format: DPROutputFormat
    content_sha256: str
    output_file_asset_id: UUID | None
    generated_by_user_id: UUID | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
