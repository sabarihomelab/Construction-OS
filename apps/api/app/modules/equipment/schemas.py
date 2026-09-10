from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.equipment.models import (
    EquipmentAssignmentStatus,
    EquipmentOwnership,
    EquipmentStatus,
    MaintenanceStatus,
    MaterialDeliveryStatus,
    MaterialStatus,
)


class EquipmentAssetCreate(BaseModel):
    asset_number: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    make: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=160)
    ownership: EquipmentOwnership = EquipmentOwnership.OWNED
    meter_unit: str | None = Field(default=None, max_length=40)
    current_meter: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)


class EquipmentAssetUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    asset_number: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    make: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=160)
    ownership: EquipmentOwnership | None = None
    status: EquipmentStatus | None = None
    meter_unit: str | None = Field(default=None, max_length=40)
    current_meter: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class EquipmentAssetRead(BaseModel):
    id: UUID
    organization_id: UUID
    asset_number: str
    name: str
    category: str | None
    make: str | None
    model: str | None
    serial_number: str | None
    ownership: EquipmentOwnership
    status: EquipmentStatus
    meter_unit: str | None
    current_meter: Decimal | None
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EquipmentAssignmentCreate(BaseModel):
    equipment_asset_id: UUID
    operator_worker_id: UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    starting_meter: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_dates(self) -> "EquipmentAssignmentCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class EquipmentAssignmentEnd(BaseModel):
    expected_revision: int = Field(ge=1)
    end_date: date
    ending_meter: Decimal | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class EquipmentAssignmentRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    equipment_asset_id: UUID
    operator_worker_id: UUID | None
    status: EquipmentAssignmentStatus
    location: str | None
    start_date: date | None
    end_date: date | None
    starting_meter: Decimal | None
    ending_meter: Decimal | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MaintenanceCreate(BaseModel):
    equipment_asset_id: UUID
    project_id: UUID | None = None
    maintenance_type: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    due_date: date | None = None
    meter_value: Decimal | None = Field(default=None, ge=0)
    meter_unit: str | None = Field(default=None, max_length=40)
    provider: str | None = Field(default=None, max_length=255)
    service_reference: str | None = Field(default=None, max_length=160)


class MaintenanceUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    status: MaintenanceStatus | None = None
    description: str | None = Field(default=None, max_length=4000)
    due_date: date | None = None
    meter_value: Decimal | None = Field(default=None, ge=0)
    meter_unit: str | None = Field(default=None, max_length=40)
    provider: str | None = Field(default=None, max_length=255)
    service_reference: str | None = Field(default=None, max_length=160)
    reason: str | None = Field(default=None, max_length=1000)


class MaintenanceRead(BaseModel):
    id: UUID
    organization_id: UUID
    equipment_asset_id: UUID
    project_id: UUID | None
    maintenance_type: str
    description: str | None
    status: MaintenanceStatus
    due_date: date | None
    started_at: datetime | None
    completed_at: datetime | None
    meter_value: Decimal | None
    meter_unit: str | None
    provider: str | None
    service_reference: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    default_unit_code: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=4000)


class MaterialUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    default_unit_code: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=4000)
    status: MaterialStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)


class MaterialRead(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    category: str | None
    default_unit_code: str
    description: str | None
    status: MaterialStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MaterialPlanWrite(BaseModel):
    material_id: UUID
    planned_quantity: Decimal = Field(ge=0)
    unit_code: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=4000)
    expected_revision: int | None = Field(default=None, ge=1)


class MaterialPlanRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    material_id: UUID
    planned_quantity: Decimal
    unit_code: str
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MaterialDeliveryCreate(BaseModel):
    material_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_code: str = Field(min_length=1, max_length=40)
    supplier: str | None = Field(default=None, max_length=255)
    ticket_number: str | None = Field(default=None, max_length=160)
    delivered_at: datetime
    status: MaterialDeliveryStatus = MaterialDeliveryStatus.PENDING
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)


class MaterialDeliveryUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    status: MaterialDeliveryStatus | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_code: str | None = Field(default=None, min_length=1, max_length=40)
    supplier: str | None = Field(default=None, max_length=255)
    ticket_number: str | None = Field(default=None, max_length=160)
    delivered_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class MaterialDeliveryRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    material_id: UUID
    quantity: Decimal
    unit_code: str
    supplier: str | None
    ticket_number: str | None
    delivered_at: datetime
    received_by_membership_id: UUID | None
    status: MaterialDeliveryStatus
    location: str | None
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
