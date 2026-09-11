import asyncio
import logging
import os
import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.field.dpr_jobs import register_dpr_report_handlers
from app.modules.jobs.handlers import JobHandlerRegistry, job_handlers
from app.modules.jobs.models import (
    BackgroundJob,
    BackgroundJobAttempt,
    JobAttemptStatus,
    JobStatus,
)
from app.modules.jobs.service import complete_job, fail_job, reclaim_expired_jobs
from app.modules.search.providers import search_projection_providers
from app.modules.search.workers import register_search_handlers
from app.runtime.deployment import RuntimePlan, build_runtime_plan

logger = logging.getLogger("construction_os.worker")


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def register_runtime_handlers(plan: RuntimePlan, registry: JobHandlerRegistry) -> None:
    if not registry.contains("search.index_entity"):
        register_search_handlers(registry, search_projection_providers)
    if plan.module_enabled("field"):
        register_dpr_report_handlers(registry)


async def _claim_next_enabled_job(
    *,
    worker_id: str,
    enabled_job_types: tuple[str, ...],
    registry: JobHandlerRegistry,
) -> UUID | None:
    if not enabled_job_types:
        return None
    current = datetime.now(UTC)
    async with SessionLocal() as db:
        job = await db.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.status.in_((JobStatus.QUEUED, JobStatus.RETRYING)),
                BackgroundJob.job_type.in_(enabled_job_types),
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

        spec = registry.get(job.job_type)
        lease_seconds = max(spec.lease_seconds, spec.timeout_seconds + 30)
        job.status = JobStatus.RUNNING
        job.attempt_count += 1
        job.lease_owner = worker_id
        job.lease_expires_at = current + timedelta(seconds=lease_seconds)
        job.heartbeat_at = current
        job.started_at = job.started_at or current
        job.last_error_code = None
        job.last_error_message = None
        db.add(
            BackgroundJobAttempt(
                organization_id=job.organization_id,
                job_id=job.id,
                attempt_number=job.attempt_count,
                worker_id=worker_id,
                status=JobAttemptStatus.RUNNING,
                heartbeat_at=current,
            )
        )
        await db.commit()
        return job.id


async def _mark_failed(job_id: UUID, *, worker_id: str, exc: Exception) -> None:
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None or job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
            return
        await fail_job(
            db,
            job,
            worker_id=worker_id,
            error_code=type(exc).__name__,
            error_message=str(exc) or type(exc).__name__,
            retryable=True,
            retry_delay_seconds=15,
        )
        await db.commit()


async def _execute_job(
    job_id: UUID,
    *,
    worker_id: str,
    registry: JobHandlerRegistry,
) -> None:
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None or job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
            return
        spec = registry.get(job.job_type)
        try:
            result = await asyncio.wait_for(spec.handler(db, job), timeout=spec.timeout_seconds)
            await complete_job(db, job, worker_id=worker_id, result=result)
            await db.commit()
            logger.info("Completed background job %s (%s)", job.id, job.job_type)
        except Exception as exc:
            await db.rollback()
            logger.exception("Background job %s (%s) failed", job.id, job.job_type)
            await _mark_failed(job_id, worker_id=worker_id, exc=exc)


async def run_worker() -> None:
    settings = get_settings()
    plan = build_runtime_plan(settings)
    register_runtime_handlers(plan, job_handlers)
    enabled_job_types = job_handlers.enabled_job_types(
        worker_profiles=set(plan.worker_profiles),
        module_keys=set(plan.module_keys),
    )
    worker_id = _worker_id()
    if not enabled_job_types:
        raise RuntimeError("No background job handlers are enabled for this runtime plan")

    logger.info(
        "Starting worker %s with profiles=%s job_types=%s",
        worker_id,
        ",".join(plan.worker_profiles),
        ",".join(enabled_job_types),
    )
    last_reclaim = datetime.min.replace(tzinfo=UTC)
    while True:
        now = datetime.now(UTC)
        if (now - last_reclaim).total_seconds() >= 30:
            async with SessionLocal() as db:
                reclaimed = await reclaim_expired_jobs(db, now=now)
                await db.commit()
            if reclaimed:
                logger.warning("Reclaimed %s expired background job lease(s)", reclaimed)
            last_reclaim = now

        job_id = await _claim_next_enabled_job(
            worker_id=worker_id,
            enabled_job_types=enabled_job_types,
            registry=job_handlers,
        )
        if job_id is None:
            await asyncio.sleep(1)
            continue
        await _execute_job(job_id, worker_id=worker_id, registry=job_handlers)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Background worker stopped")


if __name__ == "__main__":
    main()
