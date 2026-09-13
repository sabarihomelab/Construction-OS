from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.equipment.usage_models import EquipmentRateBasis, EquipmentUsageStatus


class ProjectEquipmentRateCreate(BaseModel):
    rate_basis: EquipmentRateBasis
    rate: Decimal = Field(ge=0)
    effective_from: date
    effective_to: date | None = None
    source_reference: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class ProjectEquipmentRateEnd(BaseModel):
    expected_revision: int = Field(ge=1)
    effective_to: date
    reason: str | None = Field(default=None, max_length=1000)


class ProjectEquipmentRateRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    equipment_assignment_id: UUID
    rate_basis: EquipmentRateBasis
    rate: Decimal
    currency_code: str
    effective_from: date
    effective_to: date | None
    source_reference: str | None
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquipmentUsageCreate(BaseModel):
    equipment_assignment_id: UUID
    usage_date: date
    shift_code: str = Field(default="day", min_length=1, max_length=40)
    wbs_code_id: UUID | None = None
    boq_item_id: UUID | None = None
    operating_hours: Decimal | None = Field(default=None, ge=0)
    meter_start: Decimal | None = Field(default=None, ge=0)
    meter_end: Decimal | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=255)
    source_reference: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_observed_usage(self):
        has_hours = self.operating_hours is not None and self.operating_hours > 0
        if (self.meter_start is None) != (self.meter_end is None):
            raise ValueError("meter_start and meter_end must be provided together")
        has_meter_delta = (
            self.meter_start is not None
            and self.meter_end is not None
            and self.meter_end > self.meter_start
        )
        if self.meter_start is not None and self.meter_end is not None and self.meter_end < self.meter_start:
            raise ValueError("meter_end cannot be less than meter_start")
        if not has_hours and not has_meter_delta:
            raise ValueError("Positive operating hours or a positive meter change is required")
        return self


class EquipmentUsagePost(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class EquipmentUsageRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    equipment_assignment_id: UUID
    usage_date: date
    shift_code: str
    wbs_code_id: UUID | None
    boq_item_id: UUID | None
    operating_hours: Decimal | None
    meter_start: Decimal | None
    meter_end: Decimal | None
    location: str | None
    source_reference: str | None
    notes: str | None
    status: EquipmentUsageStatus
    revision: int
    created_by_membership_id: UUID
    posted_by_membership_id: UUID | None
    posted_at: datetime | None
    reversed_by_membership_id: UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
