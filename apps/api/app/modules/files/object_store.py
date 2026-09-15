import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import get_settings


class ObjectStoreError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredBinary:
    provider_key: str
    storage_key: str
    size_bytes: int
    sha256: str
    content_type: str | None


class LocalGeneratedObjectStore:
    provider_key = "local"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, storage_key: str) -> Path:
        normalized = storage_key.strip().lstrip("/")
        if not normalized:
            raise ObjectStoreError("Storage key cannot be empty")
        candidate = (self.root / normalized).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ObjectStoreError("Storage key escapes the configured storage root")
        return candidate

    async def write_bytes(
        self,
        *,
        organization_id: UUID,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> StoredBinary:
        if not content:
            raise ObjectStoreError("Generated file content cannot be empty")
        safe_name = Path(filename).name.strip()
        if not safe_name:
            raise ObjectStoreError("Generated filename is required")
        object_id = uuid4()
        storage_key = f"organizations/{organization_id}/generated/{object_id}/{safe_name}"
        target = self._path(storage_key)
        temporary = target.with_name(f".{target.name}.{uuid4()}.tmp")

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(content)
            temporary.replace(target)

        await asyncio.to_thread(_write)
        return StoredBinary(
            provider_key=self.provider_key,
            storage_key=storage_key,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content_type=content_type,
        )

    async def read_bytes(self, storage_key: str) -> bytes:
        target = self._path(storage_key)
        if not target.is_file():
            raise ObjectStoreError("Stored file was not found")
        return await asyncio.to_thread(target.read_bytes)


_local_store: LocalGeneratedObjectStore | None = None


def generated_object_store() -> LocalGeneratedObjectStore:
    global _local_store
    settings = get_settings()
    provider = settings.storage_provider.strip().lower()
    if provider != "local":
        raise ObjectStoreError(
            f"Generated file writes are not configured for STORAGE_PROVIDER={settings.storage_provider!r}; "
            "install the corresponding object-store adapter first"
        )
    if _local_store is None:
        _local_store = LocalGeneratedObjectStore(Path(settings.storage_local_root))
    return _local_store
