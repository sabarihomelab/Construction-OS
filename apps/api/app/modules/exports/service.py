from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.exports.models import DataExportRequest, ExportScopeType, ExportStatus
from app.modules.jobs.service import enqueue_job


class ExportValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExportContext:
    organization_id: UUID
    scope_type: ExportScopeType
    scope_id: str | None
    include_files: bool
    include_audit: bool
    options: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ExportChunk:
    module_key: str
    entity_type: str
    relative_path: str
    schema_version: int
    record_count: int
    file_count: int = 0
    checksum_sha256: str | None = None
    metadata: Mapping[str, object] | None = None


ExportProvider = Callable[[AsyncSession, ExportContext], Awaitable[list[ExportChunk]]]


class ExportProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ExportProvider] = {}

    def register(self, module_key: str, provider: ExportProvider) -> None:
        key = module_key.strip()
        if not key:
            raise ValueError("module_key is required")
        if key in self._providers:
            raise ValueError(f"Export provider already registered for {key}")
        self._providers[key] = provider

    def items(self) -> tuple[tuple[str, ExportProvider], ...]:
        return tuple(sorted(self._providers.items()))


async def request_data_export(
    db: AsyncSession,
    *,
    organization_id: UUID,
    requested_by_user_id: UUID,
    scope_type: ExportScopeType,
    scope_id: str | None,
    include_files: bool = True,
    include_audit: bool = False,
    options: Mapping[str, object] | None = None,
    retention: timedelta = timedelta(days=7),
    session_id: UUID | None = None,
) -> DataExportRequest:
    normalized_scope_id = scope_id.strip() if scope_id else None
    if scope_type == ExportScopeType.COMPANY and normalized_scope_id is not None:
        raise ExportValidationError("Company export must not provide scope_id")
    if scope_type != ExportScopeType.COMPANY and normalized_scope_id is None:
        raise ExportValidationError("Scoped export requires scope_id")
    if retention <= timedelta(0):
        raise ExportValidationError("Export retention must be positive")

    request = DataExportRequest(
        organization_id=organization_id,
        requested_by_user_id=requested_by_user_id,
        scope_type=scope_type,
        scope_id=normalized_scope_id,
        status=ExportStatus.QUEUED,
        include_files=include_files,
        include_audit=include_audit,
        manifest_version=1,
        options=dict(options or {}),
        expires_at=datetime.now(UTC) + retention,
    )
    db.add(request)
    await db.flush()

    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="exports.build",
        payload={"export_request_id": str(request.id)},
        idempotency_key=f"exports.build:{request.id}",
        created_by_user_id=requested_by_user_id,
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="data_export.requested",
        target_type="data_export_request",
        target_id=str(request.id),
        actor_type=AuditActorType.USER,
        actor_user_id=requested_by_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "scope_type": scope_type.value,
            "scope_id": normalized_scope_id,
            "include_files": include_files,
            "include_audit": include_audit,
        },
    )
    return request


def validate_export_chunk(chunk: ExportChunk) -> None:
    if not chunk.module_key.strip() or not chunk.entity_type.strip():
        raise ExportValidationError("Export chunk module and entity type are required")
    if not chunk.relative_path.strip() or chunk.relative_path.startswith("/"):
        raise ExportValidationError("Export chunk path must be relative")
    if ".." in chunk.relative_path.split("/"):
        raise ExportValidationError("Export chunk path cannot traverse directories")
    if chunk.schema_version < 1 or chunk.record_count < 0 or chunk.file_count < 0:
        raise ExportValidationError("Export chunk counts and schema version are invalid")
    if chunk.checksum_sha256 is not None:
        digest = chunk.checksum_sha256.lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ExportValidationError("Export chunk checksum must be SHA-256")
