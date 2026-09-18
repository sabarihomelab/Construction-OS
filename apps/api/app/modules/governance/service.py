from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.governance.models import (
    DataLifecyclePolicy,
    DataLifecyclePolicyVersion,
    LegalHold,
    LegalHoldStatus,
    LifecycleRun,
    LifecycleRunStatus,
    PolicyVersionStatus,
)
from app.modules.jobs.service import enqueue_job


class GovernanceValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LifecycleAnalysis:
    candidate_count: int
    blocked_count: int
    summary: Mapping[str, object]


LifecycleAnalyzer = Callable[
    [AsyncSession, UUID, DataLifecyclePolicyVersion, str, str], Awaitable[LifecycleAnalysis]
]


class LifecycleAnalyzerRegistry:
    def __init__(self) -> None:
        self._analyzers: dict[str, LifecycleAnalyzer] = {}

    def register(self, entity_type: str, analyzer: LifecycleAnalyzer) -> None:
        key = entity_type.strip()
        if not key:
            raise ValueError("entity_type is required")
        if key in self._analyzers:
            raise ValueError(f"Lifecycle analyzer already registered for {key}")
        self._analyzers[key] = analyzer

    def get(self, entity_type: str) -> LifecycleAnalyzer:
        try:
            return self._analyzers[entity_type]
        except KeyError as exc:
            raise GovernanceValidationError(
                f"No lifecycle analyzer registered for {entity_type}"
            ) from exc


async def has_active_legal_hold(
    db: AsyncSession,
    *,
    organization_id: UUID,
    scope_type: str,
    scope_id: str,
) -> bool:
    hold = await db.scalar(
        select(LegalHold.id).where(
            LegalHold.organization_id == organization_id,
            LegalHold.scope_type == scope_type,
            LegalHold.scope_id == scope_id,
            LegalHold.status == LegalHoldStatus.ACTIVE,
        )
    )
    return hold is not None


async def publish_lifecycle_policy_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    policy_version_id: UUID,
    actor_user_id: UUID,
) -> DataLifecyclePolicyVersion:
    version = await db.scalar(
        select(DataLifecyclePolicyVersion)
        .where(
            DataLifecyclePolicyVersion.id == policy_version_id,
            DataLifecyclePolicyVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if version is None or version.status != PolicyVersionStatus.DRAFT:
        raise GovernanceValidationError("Draft lifecycle policy version was not found")

    policy = await db.scalar(
        select(DataLifecyclePolicy)
        .where(
            DataLifecyclePolicy.id == version.policy_id,
            DataLifecyclePolicy.organization_id == organization_id,
            DataLifecyclePolicy.active.is_(True),
        )
        .with_for_update()
    )
    if policy is None:
        raise GovernanceValidationError("Active lifecycle policy was not found")

    previous = list(
        (
            await db.scalars(
                select(DataLifecyclePolicyVersion).where(
                    DataLifecyclePolicyVersion.organization_id == organization_id,
                    DataLifecyclePolicyVersion.policy_id == policy.id,
                    DataLifecyclePolicyVersion.status == PolicyVersionStatus.ACTIVE,
                )
            )
        ).all()
    )
    for active in previous:
        active.status = PolicyVersionStatus.RETIRED

    current = datetime.now(UTC)
    version.status = PolicyVersionStatus.ACTIVE
    version.effective_from = version.effective_from or current
    version.published_at = current
    version.published_by_user_id = actor_user_id
    policy.current_version = version.version
    await db.flush()
    return version


async def analyze_lifecycle_run(
    db: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    analyzers: LifecycleAnalyzerRegistry,
) -> LifecycleRun:
    run = await db.scalar(
        select(LifecycleRun)
        .where(LifecycleRun.id == run_id, LifecycleRun.organization_id == organization_id)
        .with_for_update()
    )
    if run is None or run.status not in {LifecycleRunStatus.DRAFT, LifecycleRunStatus.BLOCKED}:
        raise GovernanceValidationError("Lifecycle run is not available for analysis")

    version = await db.scalar(
        select(DataLifecyclePolicyVersion).where(
            DataLifecyclePolicyVersion.id == run.policy_version_id,
            DataLifecyclePolicyVersion.organization_id == organization_id,
            DataLifecyclePolicyVersion.status == PolicyVersionStatus.ACTIVE,
        )
    )
    if version is None:
        raise GovernanceValidationError("Active lifecycle policy version was not found")
    policy = await db.scalar(
        select(DataLifecyclePolicy).where(
            DataLifecyclePolicy.id == version.policy_id,
            DataLifecyclePolicy.organization_id == organization_id,
        )
    )
    if policy is None:
        raise GovernanceValidationError("Lifecycle policy was not found")

    run.status = LifecycleRunStatus.ANALYZING
    await db.flush()
    analysis = await analyzers.get(policy.entity_type)(
        db,
        organization_id,
        version,
        run.scope_type,
        run.scope_id,
    )
    if analysis.candidate_count < 0 or analysis.blocked_count < 0:
        raise GovernanceValidationError("Lifecycle analysis returned invalid counts")
    if analysis.blocked_count > analysis.candidate_count:
        raise GovernanceValidationError("Blocked lifecycle count cannot exceed candidates")

    run.candidate_count = analysis.candidate_count
    run.blocked_count = analysis.blocked_count
    run.analysis = dict(analysis.summary)
    run.status = LifecycleRunStatus.BLOCKED if analysis.blocked_count else LifecycleRunStatus.READY
    await db.flush()
    return run


async def queue_lifecycle_application(
    db: AsyncSession,
    *,
    organization_id: UUID,
    run_id: UUID,
    actor_user_id: UUID,
) -> LifecycleRun:
    run = await db.scalar(
        select(LifecycleRun)
        .where(LifecycleRun.id == run_id, LifecycleRun.organization_id == organization_id)
        .with_for_update()
    )
    if run is None or run.status != LifecycleRunStatus.READY:
        raise GovernanceValidationError("Lifecycle run must be analyzed and unblocked first")
    if await has_active_legal_hold(
        db,
        organization_id=organization_id,
        scope_type=run.scope_type,
        scope_id=run.scope_id,
    ):
        run.status = LifecycleRunStatus.BLOCKED
        await db.flush()
        raise GovernanceValidationError("Lifecycle run is blocked by an active legal hold")

    run.status = LifecycleRunStatus.APPLYING
    await enqueue_job(
        db,
        organization_id=organization_id,
        job_type="governance.apply_lifecycle",
        payload={"lifecycle_run_id": str(run.id)},
        idempotency_key=f"governance.apply_lifecycle:{run.id}",
        created_by_user_id=actor_user_id,
    )
    await db.flush()
    return run
