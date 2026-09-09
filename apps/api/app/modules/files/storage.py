from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UploadTarget:
    storage_key: str
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DownloadTarget:
    url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class StoredObjectInfo:
    storage_key: str
    size_bytes: int
    sha256: str
    detected_content_type: str | None


class StorageProvider(Protocol):
    @property
    def provider_key(self) -> str: ...

    async def create_upload_target(
        self,
        *,
        storage_key: str,
        content_type: str | None,
        expected_size_bytes: int | None,
        expires_at: datetime,
    ) -> UploadTarget: ...

    async def inspect_object(self, storage_key: str) -> StoredObjectInfo: ...

    async def create_download_target(
        self,
        *,
        storage_key: str,
        expires_at: datetime,
        download_name: str | None = None,
    ) -> DownloadTarget: ...

    async def delete_object(self, storage_key: str) -> None: ...


class StorageProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, StorageProvider] = {}

    def register(self, provider: StorageProvider) -> None:
        key = provider.provider_key.strip()
        if not key:
            raise ValueError("Storage provider key cannot be empty")
        if key in self._providers:
            raise ValueError(f"Storage provider is already registered: {key}")
        self._providers[key] = provider

    def get(self, provider_key: str) -> StorageProvider:
        try:
            return self._providers[provider_key]
        except KeyError as exc:
            raise KeyError(f"Unknown storage provider: {provider_key}") from exc
