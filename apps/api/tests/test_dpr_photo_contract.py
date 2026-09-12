import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.modules.field.dpr_photo_schemas import DPRPhotoUploadStart
from app.modules.files.local_provider import LocalStorageProvider, LocalStorageProviderError


PHOTO_ROUTE_PREFIX = "/api/v1/projects/{project_id}/daily-reports/{report_id}/photos"


def test_dpr_photo_routes_are_mounted() -> None:
    paths = {route.path for route in create_app().routes}
    assert PHOTO_ROUTE_PREFIX in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/content" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/finalize" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/{{asset_id}}" in paths


def test_dpr_photo_start_requires_revision_and_limits_size() -> None:
    payload = {
        "expected_revision": 3,
        "client_photo_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "original_filename": "site.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 1024,
        "sha256": "a" * 64,
    }
    parsed = DPRPhotoUploadStart.model_validate(payload)
    assert parsed.expected_revision == 3

    with pytest.raises(ValidationError):
        DPRPhotoUploadStart.model_validate({**payload, "size_bytes": 25 * 1024 * 1024 + 1})

    with pytest.raises(ValidationError):
        DPRPhotoUploadStart.model_validate({key: value for key, value in payload.items() if key != "expected_revision"})


def test_local_upload_provider_rejects_path_escape(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path)
    with pytest.raises(LocalStorageProviderError):
        provider._path("../../outside.jpg")  # noqa: SLF001


@pytest.mark.asyncio
async def test_local_upload_provider_writes_and_inspects_bytes(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path)
    content = b"construction-os-photo"
    storage_key = "organizations/test/objects/photo-1"

    await provider.write_upload_bytes(storage_key=storage_key, content=content)
    info = await provider.inspect_object(storage_key)

    assert info.storage_key == storage_key
    assert info.size_bytes == len(content)
    assert info.sha256 == hashlib.sha256(content).hexdigest()
