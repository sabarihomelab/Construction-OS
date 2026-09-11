from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.field.dpr_models import DPRWorkProgressSourceType
from app.modules.reporting.template_models import TemplateOutputFormat


class DPRWorkProgressWrite(BaseModel):
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    location: str | None = Field(default=None, max_length=255)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_code: str | None = Field(default=None, max_length=40)
    progress_percent: Decimal | None = Field(default=None, ge=0, le=100)
    source_type: DPRWorkProgressSourceType = DPRWorkProgressSourceType.MANUAL
    source_id: UUID | None = None
    source_revision: int | None = Field(default=None, ge=1)
    remarks: str | None = None
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_control_reference(self) -> "DPRWorkProgressWrite":
        if self.wbs_code_id is None and self.boq_item_id is None:
            raise ValueError("Work progress requires a WBS / Cost Code or BOQ Item")
        if self.source_type == DPRWorkProgressSourceType.MANUAL:
            if self.source_id is not None or self.source_revision is not None:
                raise ValueError("Manual work progress cannot supply source_id/source_revision")
        elif self.source_id is None:
            raise ValueError("Non-manual work progress requires source_id")
        return self


class DPRWorkProgressReplace(BaseModel):
    expected_revision: int = Field(ge=1)
    rows: list[DPRWorkProgressWrite] = Field(default_factory=list, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid")


class DPRWorkProgressRead(DPRWorkProgressWrite):
    id: UUID
    organization_id: UUID
    project_id: UUID
    daily_report_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DPRReportPayloadRead(BaseModel):
    report_type_key: str = "field.dpr"
    report_id: UUID
    payload: dict[str, object]


class DPRRenderRequest(BaseModel):
    output_format: TemplateOutputFormat
    template_version_id: UUID | None = None
    persist_history: bool = True
    model_config = ConfigDict(extra="forbid")
