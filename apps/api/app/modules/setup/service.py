from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.jobs.service import enqueue_job
from app.modules.setup.models import (
    ConfigurationHealthCheck,
    ConfigurationHealthStatus,
    ConfigurationTemplate,
    ConfigurationTemplateVersion,
    SetupRun,
    SetupRunStatus,
    TemplateVersionStatus,
)


class SetupValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TemplateValidationResult:
    valid: bool
    summary: dict[str, object]


TemplateValidator = Callable[
    [AsyncSession, UUID, Mapping[str, object]], Awaitable[TemplateValidationResult]
]
TemplateApplier = Callable[
    [AsyncSession, UUID, str | None, Mapping[str, object]], Awaitable[dict[str, object]]
]


@dataclass(frozen=True, slots=True)
class TemplateProvider:
    target_type: str
    validate: TemplateValidator
    apply: TemplateApplier


class TemplateProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, TemplateProvider] = {}

    def register(self, provider: TemplateProvider) -> None:
        if provider.target_type in self._providers:
            raise ValueError(f"Template provider already registered for {provider.target_type}")
        self._providers[provider.target_type] = provider

    def get(self, target_type: str) -> TemplateProvider:
        try:
            return self._providers[target_type]
        except KeyError as exc:
            raise SetupValidationError(f"Unsupported setup target type: {target_type}") from exc


async def publish_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    template_version_id: UUID,
    actor_user_id: UUID,
    providers: TemplateProviderRegistry,
    session_id: UUID | None = None,
) -> ConfigurationTemplateVersion:
    version = await db.scalar(
        select(ConfigurationTemplateVersion)
        .where(
            ConfigurationTemplateVersion.id == template_version_id,
            ConfigurationTemplateVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if version is None:
        raise SetupValidationError("Template version was not found")
    if version.status != TemplateVersionStatus.DRAFT:
        raise SetupValidationError("Only draft template versions can be published")

    template = await db.scalar(
        select(ConfigurationTemplate)
        .where(
            ConfigurationTemplate.id == version.template_id,
            ConfigurationTemplate.organization_id == organization_id,
            ConfigurationTemplate.active.is_(True),
        )
        .with_for_update()
    )
    if template is None:
        raise SetupValidationError("Active template was not found")

    provider = providers.get(template.target_type)
    validation = await provider.validate(db, organization_id, version.payload)
    if not validation.valid:
        raise SetupValidationError("Template validation failed")

    active_versions = list(
        (
            await db.scalars(
                select(ConfigurationTemplateVersion).where(
                    ConfigurationTemplateVersion.organization_id == organization_id,
                    ConfigurationTemplateVersion.template_id == template.id,
                    ConfigurationTemplateVersion.status == TemplateVersionStatus.ACTIVE,
                )
            )
        ).all()
    )
    for active in active_versions:
        active.status = TemplateVersionStatus.RETIRED

    version.status = TemplateVersionStatus.ACTIVE
    version.published_at = datetime.now(UTC)
    version.published_by_user_id = actor_user_id
    template.current_version = version.version
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="setup.template_version.published",
        target_type="configuration_template",
        target_id=str(template.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"version": version.version, "target_type": template.target_type},
    )
    return version


async def create_setup_run(
    db: AsyncSession,
    *,
    organization_id: UUID,
    setup_type: str,
    target_id: str | None,
    template_version_id: UUID | None,
    actor_user_id: UUID,
) -> SetupRun:
    run = SetupRun(
        organization_id=organization_id,
        setup_type=setup_type.strip(),
        target_id=target_id.strip() if target_id else None,
        template_version_id=template_version_id,
        status=SetupRunStatus.DRAFT,
        initiated_by_user_id=actor_user_id,
    )
    db.add(run)
    await db.flush()
    return run


async def validate_setup_run(
    db: AsyncSession,
    *,
    run_id: UUID,
    organization_id: UUID,
    providers: TemplateProviderRegistry,
    expected_revision: int,
) -> SetupRun:
    run = await db.scalar(
        select(SetupRun)
        .where(SetupRun.id == run_id, SetupRun.organization_id == organization_id)
        .with_for_update()
    )
    if run is None:
        raise SetupValidationError("Setup run was not found")
    if run.revision != expected_revision:
        raise SetupValidationError("Setup run has changed; refresh before continuing")
    if run.template_version_id is None:
        raise SetupValidationError("A template version is required for this setup run")

    version = await db.scalar(
        select(ConfigurationTemplateVersion).where(
            ConfigurationTemplateVersion.id == run.template_version_id,
            ConfigurationTemplateVersion.organization_id == organization_id,
            ConfigurationTemplateVersion.status == TemplateVersionStatus.ACTIVE,
        )
    )
    if version is None:
        raise SetupValidationError("Published template version was not found")
    template = await db.scalar(
        select(ConfigurationTemplate).where(
            ConfigurationTemplate.id == version.template_id,
            ConfigurationTemplate.organization_id == organization_id,
            ConfigurationTemplate.active.is_(True),
        )
    )
    if template is None or template.target_type != run.setup_type:
        raise SetupValidationError("Setup run target does not match the selected template")

    run.status = SetupRunStatus.VALIDATING
    await db.flush()
    validation = await providers.get(template.target_type).validate(db, organization_id, version.payload)
    run.validation_summary = validation.summary
    run.status = SetupRunStatus.READY if validation.valid else SetupRunStatus.FAILED
    run.revision += 1
    await db.flush()
    return run


async def queue_setup_application(
    db: AsyncSession,
    *,
    run_id: UUID,
    organization_id: UUID,
    expected_revision: int,
) -> SetupRun:
    run = await db.scalar(
        select(SetupRun)
        .where(SetupRun.id == run_id, SetupRun.organization_id == organization_id)
        .with_for_update()
    )
    if run is None:
        raise SetupValidationError("Setup run was not found")
    if run.revision != expected_revision or run.status != SetupRunStatus.READY:
        raise SetupValidationError("Setup run is not ready to apply")

    run.status = SetupRunStatus.APPLYING
    run.revision += 1
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="setup.apply",
        payload={"setup_run_id": str(run.id)},
        idempotency_key=f"setup.apply:{run.id}:{run.revision}",
    )
    await db.flush()
    return run


async def upsert_configuration_health(
    db: AsyncSession,
    *,
    organization_id: UUID,
    check_key: str,
    target_type: str,
    target_id: str,
    status: ConfigurationHealthStatus,
    summary: str,
    details: Mapping[str, object] | None = None,
) -> ConfigurationHealthCheck:
    row = await db.scalar(
        select(ConfigurationHealthCheck).where(
            ConfigurationHealthCheck.organization_id == organization_id,
            ConfigurationHealthCheck.check_key == check_key,
            ConfigurationHealthCheck.target_type == target_type,
            ConfigurationHealthCheck.target_id == target_id,
        )
    )
    if row is None:
        row = ConfigurationHealthCheck(
            organization_id=organization_id,
            check_key=check_key,
            target_type=target_type,
            target_id=target_id,
            status=status,
            summary=summary[:255],
            details=dict(details or {}),
            checked_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.status = status
        row.summary = summary[:255]
        row.details = dict(details or {})
        row.checked_at = datetime.now(UTC)
    await db.flush()
    return row
