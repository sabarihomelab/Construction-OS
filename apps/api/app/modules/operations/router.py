from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.jobs.models import BackgroundJob, JobStatus
from app.modules.operations.models import (
    HealthState,
    OperationalEvent,
    OperationalHealthSnapshot,
)
from app.modules.sessions.deps import CurrentSession

router = APIRouter(prefix="/admin/operations", tags=["admin-operations"])


class OperationsHealthRead(BaseModel):
    category: str
    component_key: str
    state: str
    summary: str
    metrics: dict[str, object]
    observed_at: datetime
    valid_until: datetime | None
    stale: bool


class OperationsEventRead(BaseModel):
    id: str
    category: str
    severity: str
    status: str
    title: str
    summary: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None
    resolution_summary: str | None


class OperationsJobFailureRead(BaseModel):
    id: str
    job_type: str
    status: str
    attempt_count: int
    max_attempts: int
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class OperationsJobsRead(BaseModel):
    counts: dict[str, int]
    oldest_pending_at: datetime | None
    recent_failures: list[OperationsJobFailureRead]


class OperationsSummaryRead(BaseModel):
    generated_at: datetime
    overall_state: str
    summary: str
    health: list[OperationsHealthRead]
    events: list[OperationsEventRead]
    jobs: OperationsJobsRead | None


def _require_permission(context, permission_key: str) -> None:
    if permission_key not in set(context.permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _category_allowed(category: str, permissions: set[str]) -> bool:
    normalized = category.lower().replace("-", "_")
    if "storage" in normalized:
        return "admin.operations.storage.view" in permissions
    if "security" in normalized:
        return "admin.operations.security.view" in permissions
    if "integration" in normalized or "connector" in normalized or "sync" in normalized:
        return "admin.operations.integrations.view" in permissions
    return True


def _overall_state(rows: list[OperationsHealthRead], current: datetime) -> str:
    rank = {
        HealthState.UNKNOWN.value: 0,
        HealthState.HEALTHY.value: 1,
        HealthState.ATTENTION.value: 2,
        HealthState.DEGRADED.value: 3,
        HealthState.CRITICAL.value: 4,
    }
    active = [row for row in rows if not row.stale]
    if not active:
        return HealthState.UNKNOWN.value
    return max(active, key=lambda row: rank.get(row.state, 0)).state


def _summary_for_state(state: str, component_count: int, event_count: int) -> str:
    if state == HealthState.CRITICAL.value:
        return "Critical operational conditions require administrator attention."
    if state == HealthState.DEGRADED.value:
        return "One or more company services are degraded and should be reviewed."
    if state == HealthState.ATTENTION.value:
        return "The environment is operating, with items that need administrator attention."
    if state == HealthState.HEALTHY.value:
        return f"Current operational telemetry is healthy across {component_count} monitored component(s)."
    if event_count:
        return "No current health snapshot is available; review recent operational events for context."
    return "No operational health snapshots have been recorded for this company yet."


@router.get("/summary", response_model=OperationsSummaryRead)
async def get_operations_summary(
    db: DbSession,
    session: CurrentSession,
) -> OperationsSummaryRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "admin.operations.view")
    permissions = set(context.permissions)
    current = datetime.now(UTC)

    snapshot_rows = await db.scalars(
        select(OperationalHealthSnapshot)
        .where(OperationalHealthSnapshot.organization_id == context.organization_id)
        .order_by(OperationalHealthSnapshot.observed_at.desc())
        .limit(500)
    )
    latest: dict[tuple[str, str], OperationalHealthSnapshot] = {}
    for row in snapshot_rows.all():
        key = (row.category, row.component_key)
        if key not in latest and _category_allowed(row.category, permissions):
            latest[key] = row

    health = [
        OperationsHealthRead(
            category=row.category,
            component_key=row.component_key,
            state=row.state.value,
            summary=row.summary,
            metrics=row.metrics or {},
            observed_at=row.observed_at,
            valid_until=row.valid_until,
            stale=row.valid_until is not None and row.valid_until < current,
        )
        for row in latest.values()
    ]

    event_rows = await db.scalars(
        select(OperationalEvent)
        .where(OperationalEvent.organization_id == context.organization_id)
        .order_by(OperationalEvent.last_seen_at.desc())
        .limit(100)
    )
    events = [
        OperationsEventRead(
            id=str(row.id),
            category=row.category,
            severity=row.severity.value,
            status=row.status.value,
            title=row.title,
            summary=row.summary,
            occurrence_count=row.occurrence_count,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            resolved_at=row.resolved_at,
            resolution_summary=row.resolution_summary,
        )
        for row in event_rows.all()
        if _category_allowed(row.category, permissions)
    ][:30]

    jobs: OperationsJobsRead | None = None
    if "admin.operations.jobs.view" in permissions:
        count_rows = await db.execute(
            select(BackgroundJob.status, func.count(BackgroundJob.id))
            .where(BackgroundJob.organization_id == context.organization_id)
            .group_by(BackgroundJob.status)
        )
        counts = {status_value.value: int(count) for status_value, count in count_rows.all()}
        oldest_pending_at = await db.scalar(
            select(func.min(BackgroundJob.created_at)).where(
                BackgroundJob.organization_id == context.organization_id,
                BackgroundJob.status.in_((JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING)),
            )
        )
        failed_rows = await db.scalars(
            select(BackgroundJob)
            .where(
                BackgroundJob.organization_id == context.organization_id,
                BackgroundJob.status == JobStatus.FAILED,
            )
            .order_by(BackgroundJob.finished_at.desc().nullslast(), BackgroundJob.created_at.desc())
            .limit(10)
        )
        jobs = OperationsJobsRead(
            counts=counts,
            oldest_pending_at=oldest_pending_at,
            recent_failures=[
                OperationsJobFailureRead(
                    id=str(row.id),
                    job_type=row.job_type,
                    status=row.status.value,
                    attempt_count=row.attempt_count,
                    max_attempts=row.max_attempts,
                    error_code=row.last_error_code,
                    created_at=row.created_at,
                    finished_at=row.finished_at,
                )
                for row in failed_rows.all()
            ],
        )

    overall = _overall_state(health, current)
    return OperationsSummaryRead(
        generated_at=current,
        overall_state=overall,
        summary=_summary_for_state(overall, len(health), len(events)),
        health=health,
        events=events,
        jobs=jobs,
    )
