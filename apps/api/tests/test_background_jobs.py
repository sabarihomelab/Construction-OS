import pytest

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.jobs.handlers import JobHandlerRegistry
from app.modules.jobs.service import JobPayloadError, sanitize_job_payload, sanitize_job_result


def test_background_job_tables_are_registered() -> None:
    assert {"background_jobs", "background_job_attempts"}.issubset(Base.metadata.tables)


def test_jobs_are_tenant_owned_and_attempts_are_tenant_consistent() -> None:
    jobs = Base.metadata.tables["background_jobs"]
    attempts = Base.metadata.tables["background_job_attempts"]
    assert not jobs.c.organization_id.nullable
    names = {constraint.name for constraint in attempts.foreign_key_constraints}
    assert "fk_background_job_attempts_job_org" in names


def test_queue_has_lease_retry_and_progress_state() -> None:
    columns = Base.metadata.tables["background_jobs"].c.keys()
    required = {
        "status",
        "priority",
        "available_at",
        "attempt_count",
        "max_attempts",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "progress_percent",
        "cancellation_requested_at",
    }
    assert required.issubset(columns)


def test_job_payload_redacts_secrets_and_binary_content() -> None:
    payload = sanitize_job_payload(
        {
            "file_id": "abc",
            "api_token": "secret-value",
            "nested": {"password": "secret", "bytes": b"payload"},
        }
    )
    assert payload["file_id"] == "abc"
    assert payload["api_token"] == "[REDACTED]"
    assert payload["nested"]["password"] == "[REDACTED]"
    assert payload["nested"]["bytes"] == "[BINARY]"


def test_job_payload_and_result_are_bounded() -> None:
    with pytest.raises(JobPayloadError):
        sanitize_job_payload({"value": "x" * (33 * 1024)})
    with pytest.raises(JobPayloadError):
        sanitize_job_result({"value": "x" * (17 * 1024)})


def test_job_operations_permissions_are_atomic() -> None:
    assert "admin.operations.jobs.view" in PERMISSIONS_BY_KEY
    assert "admin.operations.jobs.manage" in PERMISSIONS_BY_KEY


def test_handler_registry_rejects_duplicate_job_type() -> None:
    async def handler(_db, _job):
        return None

    registry = JobHandlerRegistry()
    registry.register("drawings.render_sheet", handler)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("drawings.render_sheet", handler)


def test_handler_registry_tracks_engine_job_types() -> None:
    async def handler(_db, _job):
        return None

    registry = JobHandlerRegistry()
    registry.register("estimate.recalculate", handler)
    registry.register("drawings.render_sheet", handler)
    assert registry.registered_job_types() == (
        "drawings.render_sheet",
        "estimate.recalculate",
    )
