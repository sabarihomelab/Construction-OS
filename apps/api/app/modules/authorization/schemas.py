from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.authorization.models import PermissionRisk
from app.modules.identity.models import MembershipKind, MembershipStatus


class PermissionDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]+(?:\.[a-z0-9_]+){2,}$", max_length=160)
    module: str = Field(min_length=1, max_length=80)
    resource: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    risk: PermissionRisk = PermissionRisk.LOW
    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]+(?:-[a-z0-9_]+)*$", min_length=2, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class RoleCreateWithPermissions(RoleCreate):
    permission_keys: set[str] = Field(default_factory=set)


class RoleRead(RoleCreate):
    id: UUID
    organization_id: UUID | None
    is_template: bool
    is_protected: bool
    is_active: bool
    version: int
    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    is_active: bool | None = None


class RolePermissionSet(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    permission_keys: set[str] = Field(default_factory=set)


class RoleClone(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]+(?:-[a-z0-9_]+)*$", min_length=2, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class RoleFromTemplate(BaseModel):
    key: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9_]+(?:-[a-z0-9_]+)*$",
        min_length=2,
        max_length=100,
    )
    name: str | None = Field(default=None, min_length=1, max_length=160)


class RoleTemplateRead(BaseModel):
    key: str
    name: str
    description: str
    scope_hint: str
    membership_kind_hint: MembershipKind
    permission_keys: list[str]


class AssignedRoleRead(BaseModel):
    id: UUID
    key: str
    name: str
    is_template: bool
    is_protected: bool


class MembershipAdminRead(BaseModel):
    id: UUID
    user_id: UUID
    primary_email: str
    display_name: str
    kind: MembershipKind
    status: MembershipStatus
    role_ids: list[UUID]
    roles: list[AssignedRoleRead]


class MembershipAdminCreate(BaseModel):
    primary_email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    kind: MembershipKind = MembershipKind.INTERNAL
    status: MembershipStatus = MembershipStatus.INVITED
    role_ids: set[UUID] = Field(default_factory=set)

    @field_validator("primary_email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        return str(value).strip().lower()


class MembershipRoleSet(BaseModel):
    role_ids: set[UUID] = Field(default_factory=set)


class MembershipStatusSet(BaseModel):
    status: MembershipStatus
