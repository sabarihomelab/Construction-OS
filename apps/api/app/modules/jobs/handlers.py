from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import BackgroundJob

JobHandler = Callable[[AsyncSession, BackgroundJob], Awaitable[dict[str, object] | None]]


@dataclass(frozen=True, slots=True)
class JobHandlerSpec:
    job_type: str
    handler: JobHandler
    timeout_seconds: int = 300
    lease_seconds: int = 60
    profile: str = "general"
    module_key: str | None = None


class JobHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandlerSpec] = {}

    def register(
        self,
        job_type: str,
        handler: JobHandler,
        *,
        timeout_seconds: int = 300,
        lease_seconds: int = 60,
        profile: str = "general",
        module_key: str | None = None,
    ) -> None:
        normalized = job_type.strip()
        normalized_profile = profile.strip().lower()
        normalized_module = module_key.strip().lower() if module_key else None
        if not normalized:
            raise ValueError("job_type is required")
        if normalized in self._handlers:
            raise ValueError(f"Job handler already registered: {normalized}")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if lease_seconds < 10:
            raise ValueError("lease_seconds must be at least 10")
        if not normalized_profile:
            raise ValueError("worker profile is required")
        self._handlers[normalized] = JobHandlerSpec(
            job_type=normalized,
            handler=handler,
            timeout_seconds=timeout_seconds,
            lease_seconds=lease_seconds,
            profile=normalized_profile,
            module_key=normalized_module,
        )

    def get(self, job_type: str) -> JobHandlerSpec:
        try:
            return self._handlers[job_type]
        except KeyError as exc:
            raise KeyError(f"No job handler registered for {job_type}") from exc

    def contains(self, job_type: str) -> bool:
        return job_type in self._handlers

    def registered_job_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def enabled_job_types(
        self,
        *,
        worker_profiles: set[str] | frozenset[str],
        module_keys: set[str] | frozenset[str],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                spec.job_type
                for spec in self._handlers.values()
                if spec.profile in worker_profiles
                and (spec.module_key is None or spec.module_key in module_keys)
            )
        )


job_handlers = JobHandlerRegistry()
