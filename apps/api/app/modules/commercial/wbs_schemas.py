from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.commercial.models import RecordStatus, WBSKind


class WBSCodeCreate(BaseModel):
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    kind: WBSKind = WBSKind.COST_CODE
    description: str | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("code", "name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class WBSCodeUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    parent_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: WBSKind | None = None
    status: RecordStatus | None = None
    description: str | None = None
    reason: str | None = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("WBS name cannot be blank")
        return value


class WBSCodeRead(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    parent_id: UUID | None
    code: str
    name: str
    kind: WBSKind
    status: RecordStatus
    description: str | None
    revision: int
    model_config = ConfigDict(from_attributes=True)


class WBSPathNode(BaseModel):
    id: UUID
    code: str
    name: str
    kind: WBSKind
    status: RecordStatus


class WBSCodeTreeRead(WBSCodeRead):
    depth: int = Field(ge=0)
    path_codes: list[str]
    child_count: int = Field(ge=0)


class WBSCodeDetailRead(WBSCodeRead):
    path: list[WBSPathNode]
    child_count: int = Field(ge=0)
    descendant_count: int = Field(ge=0)
    direct_usage_count: int = Field(ge=0)
    subtree_usage_count: int = Field(ge=0)
    usage_areas: list[str]
    structure_locked: bool
