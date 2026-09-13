from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DPRPhotoResumableStart(BaseModel):
    expected_revision: int = Field(ge=1)
    client_photo_id: UUID
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)
    sha256: str = Field(min_length=64, max_length=64)


class DPRPhotoResumableSessionRead(BaseModel):
    upload_id: UUID
    client_photo_id: UUID
    status: str
    uploaded_bytes: int
    size_bytes: int
    chunk_size_bytes: int
    content_already_present: bool
    expires_at: datetime
    finalized_asset_id: UUID | None = None
    finalized_version: int | None = None


class DPRPhotoChunkRead(BaseModel):
    upload_id: UUID
    status: str
    uploaded_bytes: int
    size_bytes: int
    complete: bool


class DPRPhotoResumableFinalize(BaseModel):
    expected_revision: int = Field(ge=1)
    client_photo_id: UUID
    caption: str | None = Field(default=None, max_length=1000)
    captured_at: datetime | None = None
