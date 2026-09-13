import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.models import (
    IngestionBatch,
    IngestionStatus,
    IntegrationConnector,
    StagedExternalRecord,
    StagedRecordStatus,
)
from app.modules.jobs.service import enqueue_job

_MAX_STAGED_PAYLOAD_BYTES = 256 * 1024
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "private_key",
)


class IntegrationValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConnectorAdapter:
    provider_type: str
    validate_configuration: Callable[[Mapping[str, object]], None]
    enqueue_sync: Callable[[AsyncSession, IntegrationConnector], Awaitable[object]]


class ConnectorAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ConnectorAdapter] = {}

    def register(self, adapter: ConnectorAdapter) -> None:
        key = adapter.provider_type.strip()
        if not key:
            raise ValueError("provider_type is required")
        if key in self._adapters:
            raise ValueError(f"Connector adapter already registered for {key}")
        self._adapters[key] = adapter

    def get(self, provider_type: str) -> ConnectorAdapter:
        try:
            return self._adapters[provider_type]
        except KeyError as exc:
            raise IntegrationValidationError(
                f"Unsupported integration provider: {provider_type}"
            ) from exc


def _sanitize_external_payload(value: object, depth: int = 0) -> object:
    if depth > 8:
        raise IntegrationValidationError("External payload nesting is too deep")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize_external_payload(raw_value, depth + 1)
        return result
    if isinstance(value, list):
        return [_sanitize_external_payload(item, depth + 1) for item in value]
    return str(value)


def canonical_external_payload(payload: Mapping[str, object]) -> tuple[dict[str, object], str]:
    sanitized = _sanitize_external_payload(payload)
    if not isinstance(sanitized, dict):
        raise IntegrationValidationError("External record payload must be an object")
    encoded = json.dumps(sanitized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    if len(encoded) > _MAX_STAGED_PAYLOAD_BYTES:
        raise IntegrationValidationError("External record exceeds staged payload limit")
    return sanitized, hashlib.sha256(encoded).hexdigest()


async def begin_ingestion_batch(
    db: AsyncSession,
    *,
    organization_id: UUID,
    connector_id: UUID,
    idempotency_key: str,
    external_batch_id: str | None = None,
    mapping_version: int = 1,
) -> IngestionBatch:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise IntegrationValidationError("Ingestion idempotency key is required")
    if mapping_version < 1:
        raise IntegrationValidationError("Mapping version must be at least 1")

    connector = await db.scalar(
        select(IntegrationConnector).where(
            IntegrationConnector.id == connector_id,
            IntegrationConnector.organization_id == organization_id,
            IntegrationConnector.enabled.is_(True),
        )
    )
    if connector is None:
        raise IntegrationValidationError("Enabled connector was not found")

    existing = await db.scalar(
        select(IngestionBatch).where(
            IngestionBatch.organization_id == organization_id,
            IngestionBatch.connector_id == connector_id,
            IngestionBatch.idempotency_key == normalized_key,
        )
    )
    if existing is not None:
        return existing

    batch = IngestionBatch(
        organization_id=organization_id,
        connector_id=connector_id,
        idempotency_key=normalized_key,
        external_batch_id=external_batch_id,
        status=IngestionStatus.RECEIVED,
        mapping_version=mapping_version,
    )
    db.add(batch)
    await db.flush()
    return batch


async def stage_external_record(
    db: AsyncSession,
    *,
    organization_id: UUID,
    batch_id: UUID,
    external_type: str,
    external_id: str,
    payload: Mapping[str, object],
    source_version: str | None = None,
) -> StagedExternalRecord:
    batch = await db.scalar(
        select(IngestionBatch)
        .where(
            IngestionBatch.id == batch_id,
            IngestionBatch.organization_id == organization_id,
        )
        .with_for_update()
    )
    if batch is None or batch.status in {
        IngestionStatus.COMMITTED,
        IngestionStatus.FAILED,
        IngestionStatus.QUARANTINED,
    }:
        raise IntegrationValidationError("Ingestion batch is not open for staging")

    normalized_type = external_type.strip()
    normalized_id = external_id.strip()
    if not normalized_type or not normalized_id:
        raise IntegrationValidationError("External type and id are required")
    normalized_payload, checksum = canonical_external_payload(payload)

    existing = await db.scalar(
        select(StagedExternalRecord).where(
            StagedExternalRecord.batch_id == batch_id,
            StagedExternalRecord.organization_id == organization_id,
            StagedExternalRecord.external_type == normalized_type,
            StagedExternalRecord.external_id == normalized_id,
        )
    )
    if existing is not None:
        if existing.payload_checksum != checksum:
            raise IntegrationValidationError(
                "External record identity was reused with different payload in the same batch"
            )
        return existing

    record = StagedExternalRecord(
        organization_id=organization_id,
        batch_id=batch_id,
        external_type=normalized_type,
        external_id=normalized_id,
        source_version=source_version,
        payload_checksum=checksum,
        payload=normalized_payload,
        status=StagedRecordStatus.STAGED,
    )
    db.add(record)
    batch.received_count += 1
    batch.status = IngestionStatus.STAGED
    await db.flush()
    return record


async def queue_ingestion_processing(
    db: AsyncSession,
    *,
    organization_id: UUID,
    batch_id: UUID,
    actor_user_id: UUID | None = None,
) -> IngestionBatch:
    batch = await db.scalar(
        select(IngestionBatch)
        .where(
            IngestionBatch.id == batch_id,
            IngestionBatch.organization_id == organization_id,
        )
        .with_for_update()
    )
    if batch is None:
        raise IntegrationValidationError("Ingestion batch was not found")
    if batch.status not in {IngestionStatus.RECEIVED, IngestionStatus.STAGED, IngestionStatus.RETRYING}:
        raise IntegrationValidationError("Ingestion batch is not ready for processing")

    batch.status = IngestionStatus.PROCESSING
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="integrations.process_batch",
        payload={"ingestion_batch_id": str(batch.id)},
        idempotency_key=f"integrations.process_batch:{batch.id}:{batch.mapping_version}",
        created_by_user_id=actor_user_id,
    )
    await db.flush()
    return batch
