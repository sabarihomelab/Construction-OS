from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.reporting.template_models import (
    TemplateOutputFormat,
    TemplateSourceKind,
    TemplateVersionStatus,
)


class ReportBrandingRead(BaseModel):
    id: UUID
    organization_id: UUID
    company_display_name: str | None
    company_logo_asset_id: UUID | None
    company_logo_version: int | None
    default_header_text: str | None
    default_footer_text: str | None
    revision: int
    updated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportBrandingUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    company_display_name: str | None = Field(default=None, max_length=255)
    company_logo_asset_id: UUID | None = None
    company_logo_version: int | None = Field(default=None, ge=1)
    default_header_text: str | None = Field(default=None, max_length=500)
    default_footer_text: str | None = Field(default=None, max_length=500)
    model_config = ConfigDict(extra="forbid")


class ReportTemplateRead(BaseModel):
    id: UUID
    organization_id: UUID
    report_type_key: str
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


class ReportTemplateVersionRead(BaseModel):
    id: UUID
    organization_id: UUID
    template_id: UUID
    version: int
    status: TemplateVersionStatus
    source_kind: TemplateSourceKind
    source_file_asset_id: UUID | None
    source_file_version: int | None
    source_format: str | None
    layout_spec: dict[str, object]
    provider_contract_version: int
    created_by_user_id: UUID | None
    published_by_user_id: UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportRenderRecordRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    report_type_key: str
    source_entity_type: str
    source_entity_id: UUID
    source_revision: int
    template_version_id: UUID
    output_format: TemplateOutputFormat
    generation_trigger: str
    content_sha256: str
    output_filename: str
    output_file_asset_id: UUID | None
    output_file_version: int | None
    issued_at: datetime | None
    generated_by_user_id: UUID | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProviderCollectionRead(BaseModel):
    key: str
    fields: list[str]


class ReportProviderContractRead(BaseModel):
    key: str
    version: int
    scalar_paths: list[str]
    collections: list[ProviderCollectionRead]
    dynamic_prefixes: list[str]
    required_permission_key: str | None


class ReportPayloadRead(BaseModel):
    report_type_key: str
    source_entity_id: UUID
    payload: dict[str, object]


class ReportRenderMetadata(BaseModel):
    template_version_id: UUID
    output_format: TemplateOutputFormat
    content_sha256: str
    filename: str
