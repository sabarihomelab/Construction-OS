from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NativeAuthenticationRequest(BaseModel):
    provider_key: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class NativeMembershipSelectionRequest(BaseModel):
    grant_token: str = Field(min_length=32, max_length=512)
    membership_id: UUID


class NativeMembershipOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    organization_id: UUID
    organization_name: str


class NativeSessionResponse(BaseModel):
    status: str = "authenticated"
    token_type: str = "Bearer"
    access_token: str
    membership_id: UUID


class NativeMembershipSelectionResponse(BaseModel):
    status: str = "membership_selection_required"
    grant_token: str
    memberships: list[NativeMembershipOption]


class NativeProviderListResponse(BaseModel):
    providers: list[str]
