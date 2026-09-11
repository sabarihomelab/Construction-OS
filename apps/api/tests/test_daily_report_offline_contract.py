from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.field.api import router as field_api_router
from app.modules.field.dpr_offline_schemas import (
    DailyReportOfflineMutationRequest,
    DailyReportOfflineOperation,
)
from app.modules.field.schemas import (
    DailyReportCreate,
    DailyReportUpdate,
    DailyReportVersionAction,
)


def _ids() -> tuple:
    return uuid4(), uuid4(), uuid4()


def test_daily_report_offline_router_is_registered() -> None:
    paths = {f"/api/v1{route.path}" for route in field_api_router.routes}
    assert "/api/v1/projects/{project_id}/daily-reports/offline/mutations" in paths


def test_daily_report_offline_create_uses_no_base_revision() -> None:
    device_id, mutation_id, local_id = _ids()
    payload = DailyReportOfflineMutationRequest(
        device_id=device_id,
        client_mutation_id=mutation_id,
        entity_id=local_id,
        operation=DailyReportOfflineOperation.CREATE_REPORT,
        create=DailyReportCreate(report_date=date(2026, 9, 12)),
    )

    assert payload.base_revision is None
    assert payload.create is not None


def test_daily_report_offline_update_requires_matching_revision() -> None:
    device_id, mutation_id, report_id = _ids()
    with pytest.raises(ValidationError, match="must match base_revision"):
        DailyReportOfflineMutationRequest(
            device_id=device_id,
            client_mutation_id=mutation_id,
            entity_id=report_id,
            operation=DailyReportOfflineOperation.UPDATE_HEADER,
            base_revision=3,
            update=DailyReportUpdate(expected_revision=2, notes="Updated"),
        )


def test_daily_report_offline_submit_requires_action_and_revision() -> None:
    device_id, mutation_id, report_id = _ids()
    payload = DailyReportOfflineMutationRequest(
        device_id=device_id,
        client_mutation_id=mutation_id,
        entity_id=report_id,
        operation=DailyReportOfflineOperation.SUBMIT,
        base_revision=4,
        action=DailyReportVersionAction(expected_revision=4),
    )

    assert payload.action is not None
    assert payload.action.expected_revision == 4


def test_daily_report_offline_operation_accepts_exactly_one_payload() -> None:
    device_id, mutation_id, report_id = _ids()
    with pytest.raises(ValidationError, match="Exactly one"):
        DailyReportOfflineMutationRequest(
            device_id=device_id,
            client_mutation_id=mutation_id,
            entity_id=report_id,
            operation=DailyReportOfflineOperation.SUBMIT,
            base_revision=1,
            update=DailyReportUpdate(expected_revision=1, notes="x"),
            action=DailyReportVersionAction(expected_revision=1),
        )
