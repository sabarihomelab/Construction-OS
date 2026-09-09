from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.metadata.models import CustomFieldType

KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
ENTITY_TYPE_PATTERN = r"^[a-z][a-z0-9_.]{0,79}$"


class CustomFieldDefinitionCreate(BaseModel):
    entity_type: str = Field(pattern=ENTITY_TYPE_PATTERN)
    key: str = Field(pattern=KEY_PATTERN)
    label: str = Field(min_length=1, max_length=160)
    field_type: CustomFieldType
    description: str | None = None
    required: bool = False
    default_value: Any | None = None
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    searchable: bool = False
    filterable: bool = False
    reportable: bool = True
    visible: bool = True
    editable: bool = True
    view_permission_key: str | None = Field(default=None, max_length=160)
    edit_permission_key: str | None = Field(default=None, max_length=160)
    display_order: int = Field(default=100, ge=0)

    @field_validator("entity_type", "key", mode="before")
    @classmethod
    def normalize_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class CustomFieldDefinitionUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    required: bool | None = None
    default_value: Any | None = None
    validation_rules: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None
    searchable: bool | None = None
    filterable: bool | None = None
    reportable: bool | None = None
    visible: bool | None = None
    editable: bool | None = None
    view_permission_key: str | None = Field(default=None, max_length=160)
    edit_permission_key: str | None = Field(default=None, max_length=160)
    display_order: int | None = Field(default=None, ge=0)
    active: bool | None = None


class CustomFieldOptionCreate(BaseModel):
    key: str = Field(pattern=KEY_PATTERN)
    label: str = Field(min_length=1, max_length=160)
    display_order: int = Field(default=100, ge=0)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value
