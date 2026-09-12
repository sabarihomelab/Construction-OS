import asyncio
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.modules.files.storage import DownloadTarget, StoredObjectInfo, UploadTarget


class LocalStorageProviderError(ValueError):
    pass


class LocalStorageProvider:
    provider_key = "local"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, storage_key: str) -> Path:
        normalized = storage_key.strip().lstrip("/")
        if not normalized:
            raise LocalStorageProviderError("Storage key cannot be empty")
        candidate = (self.root / normalized).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise LocalStorageProviderError("Storage key escapes the configured storage root")
        return candidate

    async def create_upload_target(
        self,
        *,
        storage_key: str,
        content_type: str | None,
        expected_size_bytes: int | None,
        expires_at: datetime,
    ) -> UploadTarget:
        del content_type, expected_size_bytes
        upload_id = storage_key.rstrip("/").rsplit("/", 1)[-1]
        return UploadTarget(
            storage_key=storage_key,
            url=f"local://upload/{upload_id}",
            method="PUT",
            headers={},
            expires_at=expires_at,
        )

    async def write_upload_bytes(self, *, storage_key: str, content: bytes) -> None:
        if not content:
            raise LocalStorageProviderError("Uploaded file cannot be empty")
        target = self._path(storage_key)
        temporary = target.with_name(f".{target.name}.uploading")

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(content)
            temporary.replace(target)

        await asyncio.to_thread(_write)

    async def write_upload_chunk(
        self,
        *,
        storage_key: str,
        offset: int,
        content: bytes,
    ) -> int:
        if offset < 0:
            raise LocalStorageProviderError("Upload offset cannot be negative")
        if not content:
            raise LocalStorageProviderError("Upload chunk cannot be empty")
        target = self._path(storage_key)

        def _append() -> int:
            target.parent.mkdir(parents=True, exist_ok=True)
            current_size = target.stat().st_size if target.exists() else 0
            if current_size != offset:
                raise LocalStorageProviderError(
                    f"Upload offset mismatch; server has {current_size} bytes"
                )
            with target.open("ab") as handle:
                handle.write(content)
                handle.flush()
            return current_size + len(content)

        return await asyncio.to_thread(_append)

    async def clone_object(self, *, source_storage_key: str, target_storage_key: str) -> None:
        source = self._path(source_storage_key)
        target = self._path(target_storage_key)
        if not source.is_file():
            raise LocalStorageProviderError("Source object was not found")

        def _copy() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

        await asyncio.to_thread(_copy)

    async def inspect_object(self, storage_key: str) -> StoredObjectInfo:
        target = self._path(storage_key)
        if not target.is_file():
            raise LocalStorageProviderError("Uploaded object was not found")

        def _inspect() -> tuple[int, str]:
            digest = hashlib.sha256()
            size = 0
            with target.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            return size, digest.hexdigest()

        size_bytes, sha256 = await asyncio.to_thread(_inspect)
        return StoredObjectInfo(
            storage_key=storage_key,
            size_bytes=size_bytes,
            sha256=sha256,
            detected_content_type=None,
        )

    async def create_download_target(
        self,
        *,
        storage_key: str,
        expires_at: datetime,
        download_name: str | None = None,
    ) -> DownloadTarget:
        del download_name
        return DownloadTarget(
            url=f"local://download/{storage_key}",
            headers={},
            expires_at=expires_at,
        )

    async def delete_object(self, storage_key: str) -> None:
        target = self._path(storage_key)
        await asyncio.to_thread(target.unlink, missing_ok=True)


_local_provider: LocalStorageProvider | None = None


def configured_storage_provider() -> LocalStorageProvider:
    global _local_provider
    settings = get_settings()
    provider_key = settings.storage_provider.strip().lower()
    if provider_key != "local":
        raise LocalStorageProviderError(
            f"STORAGE_PROVIDER={settings.storage_provider!r} does not have an installed upload adapter"
        )
    if _local_provider is None:
        _local_provider = LocalStorageProvider(Path(settings.storage_local_root))
    return _local_provider
