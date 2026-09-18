# ruff: noqa: I001

import hashlib
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.modules.field.dpr_photo_schemas import DPRPhotoUploadStart
from app.modules.files.jobs import FILE_PROCESS_JOB_TYPE
from app.modules.files.local_provider import LocalStorageProvider, LocalStorageProviderError
from app.modules.files.resumable_service import request_hash
from app.modules.jobs.handlers import JobHandlerRegistry
from app.runtime.deployment import build_runtime_plan
from app.runtime.worker import register_runtime_handlers


PHOTO_ROUTE_PREFIX = "/api/v1/projects/{project_id}/daily-reports/{report_id}/photos"


def test_dpr_photo_routes_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    assert PHOTO_ROUTE_PREFIX in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/content" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/finalize" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/{{asset_id}}" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/resumable" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/status" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/chunk" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/resumable-finalize" in paths
    assert f"{PHOTO_ROUTE_PREFIX}/uploads/{{upload_id}}/resumable" in paths


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
        DPRPhotoUploadStart.model_validate(
            {key: value for key, value in payload.items() if key != "expected_revision"}
        )


def test_resumable_request_hash_is_stable_and_metadata_bound() -> None:
    context_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    first = request_hash(
        context_type="daily_report_photo",
        context_id=context_id,
        filename="site.jpg",
        content_type="image/jpeg",
        size_bytes=12345,
        sha256="a" * 64,
    )
    repeated = request_hash(
        context_type="daily_report_photo",
        context_id=context_id,
        filename="site.jpg",
        content_type="image/jpeg",
        size_bytes=12345,
        sha256="a" * 64,
    )
    changed = request_hash(
        context_type="daily_report_photo",
        context_id=context_id,
        filename="site.jpg",
        content_type="image/jpeg",
        size_bytes=12346,
        sha256="a" * 64,
    )

    assert len(first) == 64
    assert first == repeated
    assert first != changed


def test_file_processing_job_is_registered_for_runtime_worker() -> None:
    registry = JobHandlerRegistry()
    register_runtime_handlers(build_runtime_plan(Settings()), registry)
    assert FILE_PROCESS_JOB_TYPE in registry.registered_job_types()


def test_local_upload_provider_rejects_path_escape(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path)
    with pytest.raises(LocalStorageProviderError):
        provider._path("../../outside.jpg")


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


@pytest.mark.asyncio
async def test_local_upload_provider_resumes_from_confirmed_offset(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path)
    storage_key = "organizations/test/objects/resumable-photo"
    first = b"first-chunk"
    second = b"second-chunk"

    confirmed = await provider.write_upload_chunk(
        storage_key=storage_key,
        offset=0,
        content=first,
    )
    assert confirmed == len(first)
    assert await provider.uploaded_size(storage_key) == len(first)

    confirmed = await provider.write_upload_chunk(
        storage_key=storage_key,
        offset=len(first),
        content=second,
    )
    assert confirmed == len(first) + len(second)

    info = await provider.inspect_object(storage_key)
    expected = first + second
    assert info.size_bytes == len(expected)
    assert info.sha256 == hashlib.sha256(expected).hexdigest()


@pytest.mark.asyncio
async def test_local_upload_provider_rejects_wrong_resume_offset(tmp_path: Path) -> None:
    provider = LocalStorageProvider(tmp_path)
    storage_key = "organizations/test/objects/resumable-photo-offset"
    await provider.write_upload_chunk(storage_key=storage_key, offset=0, content=b"abc")

    with pytest.raises(LocalStorageProviderError, match="server has 3 bytes"):
        await provider.write_upload_chunk(storage_key=storage_key, offset=1, content=b"def")
