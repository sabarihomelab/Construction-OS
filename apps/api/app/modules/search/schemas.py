from datetime import datetime

from pydantic import BaseModel, Field


class SearchProjection(BaseModel):
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: str = Field(min_length=1, max_length=160)
    entity_version: int | None = Field(default=None, ge=1)
    required_permission_key: str | None = Field(default=None, max_length=160)
    scope_type: str | None = Field(default=None, max_length=40)
    scope_id: str | None = Field(default=None, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    body: str = Field(default="", max_length=50000)
    keywords: list[str] = Field(default_factory=list, max_length=100)
    route_hint: str | None = Field(default=None, max_length=500)
    source_updated_at: datetime | None = None


class SearchResult(BaseModel):
    entity_type: str
    entity_id: str
    entity_version: int | None
    title: str
    subtitle: str | None
    route_hint: str | None
    rank: float
