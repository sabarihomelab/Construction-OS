from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.field.dpr_offline_router import _permission_for
from app.modules.field.dpr_offline_router import router as dpr_offline_router
from app.modules.field.dpr_offline_schemas import (
    DailyReportDelayReplace,
    DailyReportOfflineMutationRequest,
    DailyReportOfflineOperation,
)
from app.modules.field.dpr_schemas import DPRWorkProgressReplace, DPRWorkProgressWrite
from app.modules.field.schemas import (
    DailyReportCreate,
    DailyReportUpdate,
    DailyReportVersionAction,
    DelayEntryWrite,
)


def _ids() -> tuple:
    return uuid4(), uuid4(), uuid4()


def test_daily_report_offline_router_is_registered() -> None:
    paths = {route.path for route in dpr_offline_router.routes}
    assert "/projects/{project_id}/daily-reports/offline/mutations" in paths


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


def test_daily_report_offline_work_progress_requires_matching_revision() -> None:
    device_id, mutation_id, report_id = _ids()
    wbs_id = uuid4()
    with pytest.raises(ValidationError, match="work_progress.expected_revision must match"):
        DailyReportOfflineMutationRequest(
            device_id=device_id,
            client_mutation_id=mutation_id,
            entity_id=report_id,
            operation=DailyReportOfflineOperation.REPLACE_WORK_PROGRESS,
            base_revision=6,
            work_progress=DPRWorkProgressReplace(
                expected_revision=5,
                rows=[
                    DPRWorkProgressWrite(
                        wbs_code_id=wbs_id,
                        description="Level 2 slab reinforcement",
                        progress_percent=65,
                    )
                ],
            ),
        )


def test_daily_report_offline_work_progress_uses_update_permission() -> None:
    device_id, mutation_id, report_id = _ids()
    wbs_id = uuid4()
    payload = DailyReportOfflineMutationRequest(
        device_id=device_id,
        client_mutation_id=mutation_id,
        entity_id=report_id,
        operation=DailyReportOfflineOperation.REPLACE_WORK_PROGRESS,
        base_revision=5,
        work_progress=DPRWorkProgressReplace(
            expected_revision=5,
            rows=[
                DPRWorkProgressWrite(
                    wbs_code_id=wbs_id,
                    description="Level 2 slab reinforcement",
                    quantity=12,
                    unit_code="t",
                    progress_percent=65,
                )
            ],
        ),
    )

    assert payload.work_progress is not None
    assert payload.work_progress.expected_revision == 5
    assert _permission_for(payload.operation) == "field.daily_report.update"


def test_daily_report_offline_delays_require_matching_revision() -> None:
    device_id, mutation_id, report_id = _ids()
    with pytest.raises(ValidationError, match="delays.expected_revision must match"):
        DailyReportOfflineMutationRequest(
            device_id=device_id,
            client_mutation_id=mutation_id,
            entity_id=report_id,
            operation=DailyReportOfflineOperation.REPLACE_DELAYS,
            base_revision=4,
            delays=DailyReportDelayReplace(
                expected_revision=3,
                rows=[
                    DelayEntryWrite(
                        category="Material",
                        description="Rebar delivery delayed",
                        lost_hours=2,
                        schedule_impact=True,
                    )
                ],
            ),
        )


def test_daily_report_offline_delays_use_update_permission() -> None:
    device_id, mutation_id, report_id = _ids()
    payload = DailyReportOfflineMutationRequest(
        device_id=device_id,
        client_mutation_id=mutation_id,
        entity_id=report_id,
        operation=DailyReportOfflineOperation.REPLACE_DELAYS,
        base_revision=4,
        delays=DailyReportDelayReplace(
            expected_revision=4,
            rows=[
                DelayEntryWrite(
                    category="RFI",
                    description="Awaiting structural clarification",
                    responsible_party="Design team",
                )
            ],
        ),
    )

    assert payload.delays is not None
    assert payload.delays.rows[0].description == "Awaiting structural clarification"
    assert _permission_for(payload.operation) == "field.daily_report.update"


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
