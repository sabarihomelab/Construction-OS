from datetime import UTC, datetime, timedelta

from app.main import app
from app.modules.operations.router import OperationsHealthRead, _category_allowed, _overall_state


def test_operations_summary_route_is_mounted() -> None:
    assert "/api/v1/admin/operations/summary" in {route.path for route in app.routes}


def test_operations_category_visibility_requires_sensitive_permissions() -> None:
    base = {"admin.operations.view"}
    assert _category_allowed("application", base)
    assert not _category_allowed("storage", base)
    assert not _category_allowed("security_posture", base)
    assert not _category_allowed("integration_sync", base)
    assert not _category_allowed("background_jobs", base)
    assert not _category_allowed("audit_events", base)

    elevated = base | {
        "admin.operations.storage.view",
        "admin.operations.security.view",
        "admin.operations.integrations.view",
        "admin.operations.jobs.view",
        "admin.operations.audit.view",
    }
    assert _category_allowed("storage", elevated)
    assert _category_allowed("security_posture", elevated)
    assert _category_allowed("integration_sync", elevated)
    assert _category_allowed("background_jobs", elevated)
    assert _category_allowed("audit_events", elevated)


def test_operations_overall_state_ignores_stale_snapshots() -> None:
    current = datetime.now(UTC)
    rows = [
        OperationsHealthRead(
            category="application",
            component_key="api",
            state="healthy",
            summary="API is healthy",
            metrics={},
            observed_at=current,
            valid_until=current + timedelta(minutes=5),
            stale=False,
        ),
        OperationsHealthRead(
            category="application",
            component_key="worker",
            state="critical",
            summary="Old snapshot",
            metrics={},
            observed_at=current - timedelta(hours=1),
            valid_until=current - timedelta(minutes=30),
            stale=True,
        ),
    ]

    assert _overall_state(rows) == "healthy"
