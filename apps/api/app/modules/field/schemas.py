from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.field.models import DailyReportHistoryType, DailyReportStatus


class DailyReportCreate(BaseModel):
    report_date: date
    shift_code: str = Field(default="day", min_length=1, max_length=40)
    weather_condition: str | None = Field(default=None, max_length=120)
    temperature_low: Decimal | None = None
    temperature_high: Decimal | None = None
    temperature_unit: str | None = Field(default=None, max_length=12)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "DailyReportCreate":
        if (
            self.temperature_low is not None
            and self.temperature_high is not None
            and self.temperature_low > self.temperature_high
        ):
            raise ValueError("temperature_low cannot exceed temperature_high")
        return self


class DailyReportUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    shift_code: str | None = Field(default=None, min_length=1, max_length=40)
    weather_condition: str | None = Field(default=None, max_length=120)
    temperature_low: Decimal | None = None
    temperature_high: Decimal | None = None
    temperature_unit: str | None = Field(default=None, max_length=12)
    notes: str | None = None
    reason: str | None = Field(default=None, max_length=1000)


class DailyReportVersionAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class DailyReportReject(DailyReportVersionAction):
    reason: str = Field(min_length=1, max_length=1000)


class DailyReportRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    report_date: date
    shift_code: str
    status: DailyReportStatus
    revision: int
    prepared_by_membership_id: UUID
    weather_condition: str | None
    temperature_low: Decimal | None
    temperature_high: Decimal | None
    temperature_unit: str | None
    notes: str | None
    workflow_instance_id: UUID | None
    configuration_context: dict[str, object]
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    voided_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CrewEntryWrite(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    trade: str | None = Field(default=None, max_length=120)
    worker_count: int = Field(default=0, ge=0, le=100000)
    regular_hours: Decimal = Field(default=Decimal(0), ge=0, le=24)
    overtime_hours: Decimal = Field(default=Decimal(0), ge=0, le=24)
    notes: str | None = None


class WorkEntryWrite(BaseModel):
    description: str = Field(min_length=1)
    location: str | None = Field(default=None, max_length=255)
    cost_code: str | None = Field(default=None, max_length=80)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_code: str | None = Field(default=None, max_length=24)
    notes: str | None = None


class EquipmentEntryWrite(BaseModel):
    equipment_name: str = Field(min_length=1, max_length=255)
    equipment_reference: str | None = Field(default=None, max_length=160)
    hours_operated: Decimal = Field(default=Decimal(0), ge=0, le=24)
    status: str | None = Field(default=None, max_length=80)
    notes: str | None = None


class DeliveryEntryWrite(BaseModel):
    supplier: str | None = Field(default=None, max_length=255)
    material: str = Field(min_length=1, max_length=255)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_code: str | None = Field(default=None, max_length=24)
    delivered_at: datetime | None = None
    ticket_number: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class ProductionEntryWrite(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    cost_code: str | None = Field(default=None, max_length=80)
    quantity: Decimal = Field(ge=0)
    unit_code: str = Field(min_length=1, max_length=24)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class DelayEntryWrite(BaseModel):
    category: str | None = Field(default=None, max_length=120)
    description: str = Field(min_length=1)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    lost_hours: Decimal | None = Field(default=None, ge=0)
    responsible_party: str | None = Field(default=None, max_length=255)
    schedule_impact: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "DelayEntryWrite":
        if self.started_at is not None and self.ended_at is not None:
            if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
                raise ValueError("Delay timestamps must include a timezone")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at cannot precede started_at")
        return self


class SafetyEntryWrite(BaseModel):
    entry_type: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1)
    severity: str | None = Field(default=None, max_length=40)
    safety_record_id: UUID | None = None
    notes: str | None = None


class DailyReportSectionsWrite(BaseModel):
    expected_revision: int = Field(ge=1)
    crew: list[CrewEntryWrite] | None = None
    work: list[WorkEntryWrite] | None = None
    equipment: list[EquipmentEntryWrite] | None = None
    deliveries: list[DeliveryEntryWrite] | None = None
    production: list[ProductionEntryWrite] | None = None
    delays: list[DelayEntryWrite] | None = None
    safety: list[SafetyEntryWrite] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class DailyReportSectionEntryRead(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CrewEntryRead(CrewEntryWrite, DailyReportSectionEntryRead):
    pass


class WorkEntryRead(WorkEntryWrite, DailyReportSectionEntryRead):
    pass


class EquipmentEntryRead(EquipmentEntryWrite, DailyReportSectionEntryRead):
    pass


class DeliveryEntryRead(DeliveryEntryWrite, DailyReportSectionEntryRead):
    pass


class ProductionEntryRead(ProductionEntryWrite, DailyReportSectionEntryRead):
    pass


class DelayEntryRead(DelayEntryWrite, DailyReportSectionEntryRead):
    pass


class SafetyEntryRead(SafetyEntryWrite, DailyReportSectionEntryRead):
    pass


class DailyReportDetailRead(DailyReportRead):
    crew: list[CrewEntryRead] = Field(default_factory=list)
    work: list[WorkEntryRead] = Field(default_factory=list)
    equipment: list[EquipmentEntryRead] = Field(default_factory=list)
    deliveries: list[DeliveryEntryRead] = Field(default_factory=list)
    production: list[ProductionEntryRead] = Field(default_factory=list)
    delays: list[DelayEntryRead] = Field(default_factory=list)
    safety: list[SafetyEntryRead] = Field(default_factory=list)


class DailyReportHistoryRead(BaseModel):
    id: UUID
    daily_report_id: UUID
    event_type: DailyReportHistoryType
    report_revision: int
    actor_user_id: UUID | None
    details: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
