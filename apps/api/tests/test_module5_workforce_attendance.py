from decimal import Decimal
from inspect import signature
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.db import model_registry as _model_registry  # noqa: F401
from app.db.base import Base
from app.modules.configuration.registry import CONFIGURATION_BY_KEY
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.offline.service import begin_mutation
from app.modules.workforce.api import router
from app.modules.workforce.attendance_schemas import (
    AttendanceEntryRead,
    AttendanceEntryWrite,
    AttendanceOfflineMutationRequest,
)
from app.runtime.modules import MODULES_BY_KEY


def _paths() -> dict[str, dict[str, object]]:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    return application.openapi()["paths"]


def test_workforce_feature_is_available_and_runtime_remains_modular() -> None:
    feature = FEATURES_BY_KEY["workforce"]
    manifest = MODULES_BY_KEY["workforce"]

    assert feature.release_state == FeatureReleaseState.AVAILABLE
    assert feature.route == "/workforce"
    assert manifest.dependencies == ("projects",)
    assert manifest.api_router == "app.modules.workforce.api:router"
    assert "commercial" in manifest.integrates_with
    assert "field" in manifest.integrates_with


def test_attendance_api_exposes_bulk_muster_and_dpr_contract() -> None:
    paths = _paths()
    root = "/api/v1/projects/{project_id}/workforce/attendance"
    detail = f"{root}/{{register_id}}"

    assert set(paths[root]) >= {"get", "post"}
    assert detail in paths
    assert f"{detail}/entries" in paths
    assert f"{detail}/submit" in paths
    assert f"{detail}/approve" in paths
    assert f"{detail}/reject" in paths
    assert f"{detail}/history" in paths
    assert f"{detail}/dpr-summary" in paths
    assert f"{root}/offline/mutations" in paths


def test_attendance_models_are_registered_with_project_safe_dimensions() -> None:
    assert "workforce_attendance_registers" in Base.metadata.tables
    assert "workforce_attendance_entries" in Base.metadata.tables
    assert "workforce_attendance_history_events" in Base.metadata.tables

    table = Base.metadata.tables["workforce_attendance_entries"]
    targets = {fk.target_fullname for fk in table.c.wbs_code_id.foreign_keys}
    assert "project_wbs_codes.id" in targets
    assert "regular_rate" not in table.c
    assert "billing_rate" not in table.c


def test_non_working_attendance_marks_cannot_carry_hours() -> None:
    with pytest.raises(ValidationError):
        AttendanceEntryWrite(
            assignment_id="00000000-0000-0000-0000-000000000001",
            mark_status="absent",
            regular_hours=Decimal(8),
        )


def test_attendance_schema_does_not_expose_sensitive_worker_rates() -> None:
    fields = set(AttendanceEntryRead.model_fields)
    assert "regular_rate" not in fields
    assert "overtime_rate" not in fields
    assert "billing_rate" not in fields
    assert "wage_basis" not in fields


def test_attendance_rules_use_shared_configuration_registry() -> None:
    for key in (
        "workforce.attendance.require_wbs",
        "workforce.attendance.approval.required",
        "workforce.attendance.workflow.definition_key",
        "workforce.attendance.workflow.approve_transition_key",
        "workforce.attendance.workflow.reject_transition_key",
        "workforce.attendance.workflow.resubmit_transition_key",
    ):
        definition = CONFIGURATION_BY_KEY[key]
        assert definition.module_key == "workforce"
        assert definition.configurable is True


def test_offline_attendance_create_uses_stable_mutation_and_temporary_entity_ids() -> None:
    request = AttendanceOfflineMutationRequest(
        device_id=uuid4(),
        client_mutation_id=uuid4(),
        entity_id=uuid4(),
        operation="create_register",
        create={
            "attendance_date": "2026-09-11",
            "shift_code": "day",
            "populate_active_workers": True,
        },
    )

    assert request.base_revision is None
    assert request.create is not None
    assert request.entries is None
    assert request.action is None


def test_offline_attendance_revision_must_match_operation_payload() -> None:
    with pytest.raises(ValidationError):
        AttendanceOfflineMutationRequest(
            device_id=uuid4(),
            client_mutation_id=uuid4(),
            entity_id=uuid4(),
            operation="replace_entries",
            base_revision=2,
            entries={"expected_revision": 3, "entries": []},
        )

    with pytest.raises(ValidationError):
        AttendanceOfflineMutationRequest(
            device_id=uuid4(),
            client_mutation_id=uuid4(),
            entity_id=uuid4(),
            operation="submit",
            base_revision=2,
            action={"expected_revision": 3},
        )


def test_offline_mutation_foundation_requires_authenticated_device_owner() -> None:
    parameters = signature(begin_mutation).parameters
    assert "organization_id" in parameters
    assert "user_id" in parameters
    assert "device_id" in parameters
    assert parameters["user_id"].default is parameters["user_id"].empty
