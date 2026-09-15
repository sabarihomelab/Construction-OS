from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DPRCustomFieldOptionRead(BaseModel):
    key: str
    label: str


class DPRCustomFieldDefinitionRead(BaseModel):
    definition_id: UUID
    key: str
    label: str
    description: str | None = None
    field_type: str
    required: bool
    editable: bool
    display_order: int
    default_value: Any | None = None
    options: list[DPRCustomFieldOptionRead] = Field(default_factory=list)


class DPRCustomFieldDefinitionsRead(BaseModel):
    project_id: UUID
    fields: list[DPRCustomFieldDefinitionRead] = Field(default_factory=list)


class DPRCustomFieldValueRead(BaseModel):
    definition_id: UUID
    value: Any | None = None


class DPRCustomFieldValuesRead(BaseModel):
    report_id: UUID
    report_revision: int = Field(ge=1)
    values: list[DPRCustomFieldValueRead] = Field(default_factory=list)


class DPRCustomFieldValueWrite(BaseModel):
    definition_id: UUID
    value: Any | None = None


class DPRCustomFieldReplace(BaseModel):
    expected_revision: int = Field(ge=1)
    values: list[DPRCustomFieldValueWrite] = Field(default_factory=list, max_length=200)
    reason: str | None = Field(default=None, max_length=1000)
