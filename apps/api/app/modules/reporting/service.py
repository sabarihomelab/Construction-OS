from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.service import enqueue_job
from app.modules.reporting.models import (
    ReportDefinition,
    ReportDefinitionVersion,
    ReportOutputFormat,
    ReportRun,
    ReportRunStatus,
    ReportVersionStatus,
)


class ReportingValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DatasetField:
    key: str
    data_type: str
    filterable: bool = True
    groupable: bool = True
    sortable: bool = True
    aggregations: tuple[str, ...] = ()
    sensitive_permission_key: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetContract:
    key: str
    fields: tuple[DatasetField, ...]
    required_permission_key: str
    default_scope_type: str | None = None


QueryValidator = Callable[[Mapping[str, object], DatasetContract], None]


@dataclass(frozen=True, slots=True)
class DatasetProvider:
    contract: DatasetContract
    validate_query: QueryValidator


class DatasetProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, DatasetProvider] = {}

    def register(self, provider: DatasetProvider) -> None:
        key = provider.contract.key.strip()
        if not key:
            raise ValueError("Dataset key is required")
        if key in self._providers:
            raise ValueError(f"Dataset provider already registered for {key}")
        self._providers[key] = provider

    def get(self, key: str) -> DatasetProvider:
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ReportingValidationError(f"Unknown reporting dataset: {key}") from exc


async def publish_report_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report_version_id: UUID,
    actor_user_id: UUID,
    datasets: DatasetProviderRegistry,
) -> ReportDefinitionVersion:
    version = await db.scalar(
        select(ReportDefinitionVersion)
        .where(
            ReportDefinitionVersion.id == report_version_id,
            ReportDefinitionVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if version is None or version.status != ReportVersionStatus.DRAFT:
        raise ReportingValidationError("Draft report version was not found")

    definition = await db.scalar(
        select(ReportDefinition)
        .where(
            ReportDefinition.id == version.definition_id,
            ReportDefinition.organization_id == organization_id,
            ReportDefinition.active.is_(True),
        )
        .with_for_update()
    )
    if definition is None:
        raise ReportingValidationError("Active report definition was not found")

    provider = datasets.get(definition.dataset_key)
    provider.validate_query(version.query_spec, provider.contract)

    current = list(
        (
            await db.scalars(
                select(ReportDefinitionVersion).where(
                    ReportDefinitionVersion.organization_id == organization_id,
                    ReportDefinitionVersion.definition_id == definition.id,
                    ReportDefinitionVersion.status == ReportVersionStatus.ACTIVE,
                )
            )
        ).all()
    )
    for active in current:
        active.status = ReportVersionStatus.RETIRED

    from datetime import UTC, datetime

    version.status = ReportVersionStatus.ACTIVE
    version.published_at = datetime.now(UTC)
    version.published_by_user_id = actor_user_id
    definition.current_version = version.version
    await db.flush()
    return version


async def request_report_run(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report_version_id: UUID,
    requested_by_user_id: UUID,
    output_format: ReportOutputFormat,
    parameters: Mapping[str, object] | None = None,
) -> ReportRun:
    version = await db.scalar(
        select(ReportDefinitionVersion).where(
            ReportDefinitionVersion.id == report_version_id,
            ReportDefinitionVersion.organization_id == organization_id,
            ReportDefinitionVersion.status == ReportVersionStatus.ACTIVE,
        )
    )
    if version is None:
        raise ReportingValidationError("Published report version was not found")

    run = ReportRun(
        organization_id=organization_id,
        report_version_id=report_version_id,
        requested_by_user_id=requested_by_user_id,
        status=ReportRunStatus.QUEUED,
        output_format=output_format,
        parameters=dict(parameters or {}),
    )
    db.add(run)
    await db.flush()
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="reporting.generate",
        payload={"report_run_id": str(run.id)},
        idempotency_key=f"reporting.generate:{run.id}",
        created_by_user_id=requested_by_user_id,
    )
    return run


def validate_standard_query_spec(query_spec: Mapping[str, object], contract: DatasetContract) -> None:
    allowed_fields = {field.key: field for field in contract.fields}
    selected = query_spec.get("fields", [])
    if not isinstance(selected, list) or not selected:
        raise ReportingValidationError("Report must select at least one field")
    for field_key in selected:
        if not isinstance(field_key, str) or field_key not in allowed_fields:
            raise ReportingValidationError(f"Unknown report field: {field_key}")

    filters = query_spec.get("filters", [])
    if not isinstance(filters, list):
        raise ReportingValidationError("Report filters must be a list")
    for item in filters:
        if not isinstance(item, Mapping):
            raise ReportingValidationError("Invalid report filter")
        key = item.get("field")
        if not isinstance(key, str) or key not in allowed_fields:
            raise ReportingValidationError("Report filter references an unknown field")
        if not allowed_fields[key].filterable:
            raise ReportingValidationError(f"Field is not filterable: {key}")

    grouping = query_spec.get("group_by", [])
    if not isinstance(grouping, list):
        raise ReportingValidationError("Report group_by must be a list")
    for key in grouping:
        if not isinstance(key, str) or key not in allowed_fields or not allowed_fields[key].groupable:
            raise ReportingValidationError(f"Field is not groupable: {key}")
