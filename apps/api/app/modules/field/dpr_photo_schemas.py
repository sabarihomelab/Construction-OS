from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DPRPhotoUploadStart(BaseModel):
    expected_revision: int = Field(ge=1)
    client_photo_id: UUID
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)
    sha256: str = Field(min_length=64, max_length=64)


class DPRPhotoUploadTargetRead(BaseModel):
    url: str
    method: str
    headers: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime


class DPRPhotoUploadSessionRead(BaseModel):
    upload_id: UUID
    client_photo_id: UUID
    target: DPRPhotoUploadTargetRead


class DPRPhotoFinalize(BaseModel):
    expected_revision: int = Field(ge=1)
    client_photo_id: UUID
    caption: str | None = Field(default=None, max_length=1000)
    captured_at: datetime | None = None


class DPRPhotoRead(BaseModel):
    asset_id: UUID
    version: int
    filename: str
    content_type: str | None
    size_bytes: int
    relation_type: str
    client_photo_id: UUID | None = None
    caption: str | None = None
    captured_at: datetime | None = None
    created_at: datetime
    report_revision: int
