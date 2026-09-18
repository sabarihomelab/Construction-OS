from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebAuthenticationRequest(BaseModel):
    provider_key: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class WebMembershipSelectionRequest(BaseModel):
    grant_token: str = Field(min_length=32, max_length=512)
    membership_id: UUID


class WebMembershipOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    organization_id: UUID
    organization_name: str


class WebSessionResponse(BaseModel):
    status: str = "authenticated"
    membership_id: UUID


class WebMembershipSelectionResponse(BaseModel):
    status: str = "membership_selection_required"
    grant_token: str
    memberships: list[WebMembershipOption]


class WebProviderListResponse(BaseModel):
    providers: list[str]
