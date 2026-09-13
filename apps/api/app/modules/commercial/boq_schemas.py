from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.commercial.models import BOQStatus


class BOQCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    currency_code: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.strip().upper()


class BOQUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("currency_code")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class BOQRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    code: str
    name: str
    description: str | None
    currency_code: str
    status: BOQStatus
    revision: int
    approved_by_membership_id: UUID | None
    approved_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class BOQItemCreate(BaseModel):
    expected_boq_revision: int | None = Field(default=None, ge=1)
    wbs_code_id: UUID | None = None
    line_number: int = Field(ge=1)
    item_code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    unit_code: str = Field(min_length=1, max_length=24)
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=3)
    rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    hsn_sac: str | None = Field(default=None, max_length=16)
    notes: str | None = None


class BOQItemUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    expected_boq_revision: int | None = Field(default=None, ge=1)
    wbs_code_id: UUID | None = None
    line_number: int | None = Field(default=None, ge=1)
    item_code: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1)
    unit_code: str | None = Field(default=None, min_length=1, max_length=24)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    hsn_sac: str | None = Field(default=None, max_length=16)
    notes: str | None = None
    reason: str | None = Field(default=None, max_length=1000)


class BOQItemRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    boq_id: UUID
    wbs_code_id: UUID | None
    line_number: int
    item_code: str
    description: str
    unit_code: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    hsn_sac: str | None
    notes: str | None
    revision: int
    model_config = ConfigDict(from_attributes=True)


class BOQDetailRead(BOQRead):
    items: list[BOQItemRead]
    total_amount: Decimal
    item_count: int
    mapped_item_count: int
    revision_count: int
    editable: bool


class BOQAction(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class BOQItemDelete(BaseModel):
    expected_revision: int = Field(ge=1)
    expected_boq_revision: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class BOQRevisionRead(BaseModel):
    id: UUID
    boq_id: UUID
    version_number: int
    approved_by_membership_id: UUID
    approved_at: datetime
    reason: str | None
    snapshot: dict[str, object]


class BOQImportPreviewRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=2_000_000)


class BOQImportApplyRequest(BOQImportPreviewRequest):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class BOQImportRowRead(BaseModel):
    row_number: int
    line_number: int | None
    item_code: str
    description: str
    unit_code: str
    quantity: Decimal | None
    rate: Decimal | None
    amount: Decimal | None
    wbs_code: str | None
    wbs_code_id: UUID | None
    hsn_sac: str | None
    notes: str | None
    errors: list[str]


class BOQImportPreviewRead(BaseModel):
    rows: list[BOQImportRowRead]
    valid_rows: int
    invalid_rows: int
    total_amount: Decimal


class BOQImportApplyRead(BaseModel):
    imported_rows: int
    total_amount: Decimal
    boq_revision: int
