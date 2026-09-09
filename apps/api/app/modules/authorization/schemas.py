from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.authorization.models import PermissionRisk


class PermissionDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]+(?:\.[a-z0-9_]+){2,}$", max_length=160)
    module: str = Field(min_length=1, max_length=80)
    resource: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    risk: PermissionRisk = PermissionRisk.LOW


class RoleCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]+(?:-[a-z0-9_]+)*$", min_length=2, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class RoleRead(RoleCreate):
    id: UUID
    organization_id: UUID | None
    is_template: bool
    is_protected: bool
    is_active: bool
    version: int
    model_config = ConfigDict(from_attributes=True)


class RolePermissionSet(BaseModel):
    permission_keys: set[str] = Field(default_factory=set)
