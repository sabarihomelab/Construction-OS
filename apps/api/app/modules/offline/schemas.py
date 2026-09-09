from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.offline.models import DevicePlatform


class DeviceRegistrationRequest(BaseModel):
    installation_id: str = Field(min_length=8, max_length=128)
    platform: DevicePlatform
    device_label: str | None = Field(default=None, max_length=160)
    app_version: str | None = Field(default=None, max_length=64)


class ClientDeviceRead(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    installation_id: str
    platform: DevicePlatform
    device_label: str | None
    app_version: str | None
    last_seen_at: datetime | None
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class EventAcknowledgementRequest(BaseModel):
    device_id: UUID
    sequence: int = Field(ge=0)


class DeviceSyncStateRead(BaseModel):
    device_id: UUID
    organization_id: UUID
    last_acknowledged_event_sequence: int = Field(ge=0)
    revision: int = Field(ge=1)
    last_sync_started_at: datetime | None
    last_sync_completed_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
