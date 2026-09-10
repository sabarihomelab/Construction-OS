import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import (
    BackgroundJob,
    BackgroundJobAttempt,
    JobAttemptStatus,
    JobStatus,
)

_MAX_JOB_PAYLOAD_BYTES = 32 * 1024
_MAX_RESULT_BYTES = 16 * 1024
_MAX_COLLECTION_ITEMS = 100
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
    "recovery_code",
)


class JobPayloadError(ValueError):
    pass


class JobStateError(ValueError):
    pass


def _sanitize(value: object, *, depth: int = 0) -> object:
    if depth > 5:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, bytes):
        return "[BINARY]"
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                result["_truncated"] = True
                break
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize(raw_value, depth=depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize(item, depth=depth + 1) for item in value[:_MAX_COLLECTION_ITEMS]]
    return str(value)[:1000]


def _bounded_object(value: Mapping[str, object] | None, *, max_bytes: int, label: str) -> dict[str, object]:
    sanitized = _sanitize(value or {})
    if not isinstance(sanitized, dict):
        raise JobPayloadError(f"{label} must be an object")
    encoded = json.dumps(sanitized, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > max_bytes:
        raise JobPayloadError(f"{label} exceeds the {max_bytes} byte safety limit")
    return sanitized


def sanitize_job_payload(value: Mapping[str, object] | None) -> dict[str, object]:
    return _bounded_object(value, max_bytes=_MAX_JOB_PAYLOAD_BYTES, label="Job payload")


def sanitize_job_result(value: Mapping[str, object] | None) -> dict[str, object]:
    return _bounded_object(value, max_bytes=_MAX_RESULT_BYTES, label="Job result")


async def enqueue_job(
    db: AsyncSession,
    *,
    organization_id: UUID,
    job_type: str,
    payload: Mapping[str, object] | None = None,
    idempotency_key: str | None = None,
    priority: int = 0,
    max_attempts: int = 5,
    available_at: datetime | None = None,
    created_by_user_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> BackgroundJob:
    if not job_type.strip():
        raise ValueError("job_type is required")
    if priority < -100 or priority > 100:
        raise ValueError("priority must be between -100 and 100")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    normalized_key = idempotency_key.strip() if idempotency_key else None
    if normalized_key:
        existing = await db.scalar(
            select(BackgroundJob).where(
                BackgroundJob.organization_id == organization_id,
                BackgroundJob.job_type == job_type,
                BackgroundJob.idempotency_key == normalized_key,
            )
        )
        if existing is not None:
            return existing

    job = BackgroundJob(
        organization_id=organization_id,
        job_type=job_type.strip(),
        payload=sanitize_job_payload(payload),
        idempotency_key=normalized_key,
        priority=priority,
        max_attempts=max_attempts,
        available_at=available_at or datetime.now(UTC),
        created_by_user_id=created_by_user_id,
        correlation_id=correlation_id,
    )
    db.add(job)
    await db.flush()
    return job


async def claim_next_job(
    db: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 60,
    now: datetime | None = None,
) -> BackgroundJob | None:
    if not worker_id.strip():
        raise ValueError("worker_id is required")
    if lease_seconds < 10:
        raise ValueError("lease_seconds must be at least 10")

    current = now or datetime.now(UTC)
    job = await db.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.status.in_((JobStatus.QUEUED, JobStatus.RETRYING)),
            BackgroundJob.available_at <= current,
            BackgroundJob.attempt_count < BackgroundJob.max_attempts,
            BackgroundJob.cancellation_requested_at.is_(None),
        )
        .order_by(
            BackgroundJob.priority.desc(),
            BackgroundJob.available_at,
            BackgroundJob.created_at,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None

    job.status = JobStatus.RUNNING
    job.attempt_count += 1
    job.lease_owner = worker_id.strip()
    job.lease_expires_at = current + timedelta(seconds=lease_seconds)
    job.heartbeat_at = current
    job.started_at = job.started_at or current
    job.last_error_code = None
    job.last_error_message = None

    attempt = BackgroundJobAttempt(
        organization_id=job.organization_id,
        job_id=job.id,
        attempt_number=job.attempt_count,
        worker_id=worker_id.strip(),
        status=JobAttemptStatus.RUNNING,
        heartbeat_at=current,
    )
    db.add(attempt)
    await db.flush()
    return job


async def heartbeat_job(
    db: AsyncSession,
    job: BackgroundJob,
    *,
    worker_id: str,
    progress_percent: int | None = None,
    progress_message: str | None = None,
    lease_seconds: int = 60,
    now: datetime | None = None,
) -> None:
    if job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
        raise JobStateError("Job is not leased by this worker")
    if progress_percent is not None and not 0 <= progress_percent <= 100:
        raise ValueError("progress_percent must be between 0 and 100")

    current = now or datetime.now(UTC)
    job.heartbeat_at = current
    job.lease_expires_at = current + timedelta(seconds=lease_seconds)
    if progress_percent is not None:
        job.progress_percent = progress_percent
    if progress_message is not None:
        job.progress_message = progress_message[:255]

    attempt = await db.scalar(
        select(BackgroundJobAttempt).where(
            BackgroundJobAttempt.job_id == job.id,
            BackgroundJobAttempt.attempt_number == job.attempt_count,
        )
    )
    if attempt is not None:
        attempt.heartbeat_at = current
        attempt.progress_percent = job.progress_percent
    await db.flush()


async def complete_job(
    db: AsyncSession,
    job: BackgroundJob,
    *,
    worker_id: str,
    result: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> None:
    if job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
        raise JobStateError("Job is not leased by this worker")

    current = now or datetime.now(UTC)
    job.status = JobStatus.SUCCEEDED
    job.result = sanitize_job_result(result)
    job.progress_percent = 100
    job.finished_at = current
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = current

    attempt = await db.scalar(
        select(BackgroundJobAttempt).where(
            BackgroundJobAttempt.job_id == job.id,
            BackgroundJobAttempt.attempt_number == job.attempt_count,
        )
    )
    if attempt is not None:
        attempt.status = JobAttemptStatus.SUCCEEDED
        attempt.progress_percent = 100
        attempt.finished_at = current
        attempt.heartbeat_at = current
    await db.flush()


async def fail_job(
    db: AsyncSession,
    job: BackgroundJob,
    *,
    worker_id: str,
    error_code: str,
    error_message: str,
    retryable: bool = True,
    retry_delay_seconds: int = 15,
    now: datetime | None = None,
) -> None:
    if job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
        raise JobStateError("Job is not leased by this worker")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds cannot be negative")

    current = now or datetime.now(UTC)
    can_retry = retryable and job.attempt_count < job.max_attempts
    job.status = JobStatus.RETRYING if can_retry else JobStatus.FAILED
    job.available_at = current + timedelta(seconds=retry_delay_seconds) if can_retry else current
    job.finished_at = None if can_retry else current
    job.lease_owner = None
    job.lease_expires_at = None
    job.last_error_code = error_code[:100]
    job.last_error_message = error_message[:4000]

    attempt = await db.scalar(
        select(BackgroundJobAttempt).where(
            BackgroundJobAttempt.job_id == job.id,
            BackgroundJobAttempt.attempt_number == job.attempt_count,
        )
    )
    if attempt is not None:
        attempt.status = JobAttemptStatus.FAILED
        attempt.error_code = error_code[:100]
        attempt.error_message = error_message[:4000]
        attempt.finished_at = current
    await db.flush()


async def request_job_cancellation(
    db: AsyncSession,
    job: BackgroundJob,
    *,
    reason: str | None = None,
    now: datetime | None = None,
) -> None:
    if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise JobStateError("Completed jobs cannot be cancelled")

    current = now or datetime.now(UTC)
    job.cancellation_requested_at = current
    job.cancellation_reason = reason[:255] if reason else None
    if job.status in (JobStatus.QUEUED, JobStatus.RETRYING):
        job.status = JobStatus.CANCELLED
        job.finished_at = current
    await db.flush()


async def reclaim_expired_jobs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    retry_delay_seconds: int = 5,
    limit: int = 100,
) -> int:
    current = now or datetime.now(UTC)
    jobs = list(
        (
            await db.scalars(
                select(BackgroundJob)
                .where(
                    BackgroundJob.status == JobStatus.RUNNING,
                    BackgroundJob.lease_expires_at.is_not(None),
                    BackgroundJob.lease_expires_at < current,
                )
                .order_by(BackgroundJob.lease_expires_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
    )

    for job in jobs:
        attempt = await db.scalar(
            select(BackgroundJobAttempt).where(
                BackgroundJobAttempt.job_id == job.id,
                BackgroundJobAttempt.attempt_number == job.attempt_count,
            )
        )
        if attempt is not None and attempt.status == JobAttemptStatus.RUNNING:
            attempt.status = JobAttemptStatus.ABANDONED
            attempt.error_code = "worker_lease_expired"
            attempt.error_message = "Worker lease expired before the attempt completed."
            attempt.finished_at = current

        job.lease_owner = None
        job.lease_expires_at = None
        job.last_error_code = "worker_lease_expired"
        job.last_error_message = "Worker lease expired before the job completed."
        if job.cancellation_requested_at is not None:
            job.status = JobStatus.CANCELLED
            job.finished_at = current
        elif job.attempt_count < job.max_attempts:
            job.status = JobStatus.RETRYING
            job.available_at = current + timedelta(seconds=retry_delay_seconds)
        else:
            job.status = JobStatus.FAILED
            job.finished_at = current

    await db.flush()
    return len(jobs)


async def count_active_jobs(db: AsyncSession, organization_id: UUID) -> int:
    rows = await db.scalars(
        select(BackgroundJob.id).where(
            BackgroundJob.organization_id == organization_id,
            or_(
                BackgroundJob.status == JobStatus.QUEUED,
                BackgroundJob.status == JobStatus.RETRYING,
                BackgroundJob.status == JobStatus.RUNNING,
            ),
        )
    )
    return len(rows.all())
