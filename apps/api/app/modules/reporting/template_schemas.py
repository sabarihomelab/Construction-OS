from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.reporting.template_models import TemplateOutputFormat, TemplateSourceKind


class PageSize(StrEnum):
    A4 = "a4"
    A3 = "a3"
    LETTER = "letter"


class PageOrientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ReportBlockKind(StrEnum):
    FIELD_GROUP = "field_group"
    TABLE = "table"
    TEXT = "text"
    IMAGE = "image"
    SIGNATURES = "signatures"
    PAGE_BREAK = "page_break"


class ConditionOperator(StrEnum):
    EXISTS = "exists"
    NON_EMPTY = "non_empty"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"
    CONTAINS = "contains"


ALLOWED_WIDTHS = {25, 30, 33, 34, 50, 67, 70, 75, 100}


class PageSpec(BaseModel):
    size: PageSize = PageSize.A4
    orientation: PageOrientation = PageOrientation.PORTRAIT
    margin_top_mm: int = Field(default=12, ge=0, le=50)
    margin_right_mm: int = Field(default=12, ge=0, le=50)
    margin_bottom_mm: int = Field(default=12, ge=0, le=50)
    margin_left_mm: int = Field(default=12, ge=0, le=50)
    model_config = ConfigDict(extra="forbid")


class HeaderFooterSpec(BaseModel):
    header_left: str | None = Field(default=None, max_length=1000)
    header_center: str | None = Field(default=None, max_length=1000)
    header_right: str | None = Field(default=None, max_length=1000)
    footer_left: str | None = Field(default=None, max_length=1000)
    footer_center: str | None = Field(default=None, max_length=1000)
    footer_right: str | None = Field(default=None, max_length=1000)
    show_page_number: bool = True
    show_generated_timestamp: bool = False
    model_config = ConfigDict(extra="forbid")


class DisplayCondition(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    operator: ConditionOperator
    value: Any | None = None
    model_config = ConfigDict(extra="forbid")


class TableColumnSpec(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=180)
    order: int = Field(default=0, ge=0, le=1000)
    visible: bool = True
    width_percent: int | None = Field(default=None, ge=5, le=100)
    align: str = Field(default="left", pattern="^(left|center|right)$")
    model_config = ConfigDict(extra="forbid")


class SortRule(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    direction: str = Field(default="asc", pattern="^(asc|desc)$")
    model_config = ConfigDict(extra="forbid")


class ReportBlock(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    kind: ReportBlockKind
    order: int = Field(ge=0, le=10000)
    row: int = Field(default=0, ge=0, le=10000)
    width_percent: int = 100
    visible: bool = True
    title: str | None = Field(default=None, max_length=300)
    data_key: str | None = Field(default=None, max_length=160)
    scalar_fields: list[str] = Field(default_factory=list, max_length=50)
    table_columns: list[TableColumnSpec] = Field(default_factory=list, max_length=80)
    sort_by: list[SortRule] = Field(default_factory=list, max_length=10)
    group_by: list[str] = Field(default_factory=list, max_length=10)
    condition: DisplayCondition | None = None
    hide_when_empty: bool = False
    page_break_before: bool = False
    repeat_table_header: bool = True
    avoid_row_split: bool = True
    keep_title_with_content: bool = True
    text_template: str | None = None
    image_placeholder: str | None = Field(default=None, max_length=200)
    photo_columns: int = Field(default=2, ge=1, le=4)
    style: dict[str, object] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_block(self) -> "ReportBlock":
        if self.width_percent not in ALLOWED_WIDTHS:
            raise ValueError(f"width_percent must be one of {sorted(ALLOWED_WIDTHS)}")
        if self.kind == ReportBlockKind.TABLE and not self.data_key:
            raise ValueError("Table blocks require data_key")
        if self.kind == ReportBlockKind.FIELD_GROUP and not self.scalar_fields:
            raise ValueError("Field-group blocks require scalar_fields")
        if self.kind == ReportBlockKind.TEXT and not (self.text_template and self.text_template.strip()):
            raise ValueError("Text blocks require text_template")
        if self.kind == ReportBlockKind.IMAGE and not self.image_placeholder:
            raise ValueError("Image blocks require image_placeholder")
        if self.kind == ReportBlockKind.PAGE_BREAK:
            self.width_percent = 100
        return self


class ReportLayoutSpec(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    report_title: str = Field(min_length=1, max_length=300)
    page: PageSpec = Field(default_factory=PageSpec)
    header_footer: HeaderFooterSpec = Field(default_factory=HeaderFooterSpec)
    blocks: list[ReportBlock]
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_layout(self) -> "ReportLayoutSpec":
        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("Report block ids must be unique")
        rows: dict[int, int] = {}
        for block in self.blocks:
            if not block.visible or block.kind == ReportBlockKind.PAGE_BREAK:
                continue
            rows[block.row] = rows.get(block.row, 0) + block.width_percent
            if rows[block.row] > 100:
                raise ValueError(f"Report row {block.row} exceeds 100% width")
        if not any(block.visible and block.kind != ReportBlockKind.PAGE_BREAK for block in self.blocks):
            raise ValueError("Report layout must contain at least one visible content block")
        return self


class ReportTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    company_wide: bool = False
    is_default: bool = False
    model_config = ConfigDict(extra="forbid")


class ReportTemplateVersionCreate(BaseModel):
    source_kind: TemplateSourceKind = TemplateSourceKind.DESIGNER
    source_file_asset_id: UUID | None = None
    source_file_version: int | None = Field(default=None, ge=1)
    source_format: str | None = Field(default=None, max_length=40)
    layout: ReportLayoutSpec
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_source(self) -> "ReportTemplateVersionCreate":
        if (self.source_file_asset_id is None) != (self.source_file_version is None):
            raise ValueError("source_file_asset_id and source_file_version must be supplied together")
        if self.source_kind == TemplateSourceKind.UPLOADED:
            if self.source_file_asset_id is None or self.source_file_version is None:
                raise ValueError("Uploaded templates must pin a File Asset version")
            if not self.source_format:
                raise ValueError("source_format is required for uploaded templates")
        return self


class ReportTemplatePublish(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid")


class ReportRenderRequest(BaseModel):
    output_format: TemplateOutputFormat
    template_version_id: UUID | None = None
    persist_history: bool = True
    model_config = ConfigDict(extra="forbid")
