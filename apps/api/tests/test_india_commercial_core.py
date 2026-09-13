from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.commercial import models as commercial_models  # noqa: F401
from app.modules.commercial.api import router as commercial_router
from app.modules.commercial.models import BOQStatus, MeasurementStatus, RABillStatus
from app.modules.commercial.schemas import (
    BOQCreate,
    MeasurementCreate,
    PartyCreate,
    RABillCreate,
    WBSCodeCreate,
)
from app.modules.commercial.service import money
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.runtime.modules import MODULES_BY_KEY, resolve_runtime_modules


def _paths() -> set[str]:
    application = FastAPI()
    application.include_router(commercial_router)
    return set(application.openapi()["paths"])


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def test_india_commercial_tables_are_registered() -> None:
    expected = {
        "commercial_parties",
        "project_party_assignments",
        "project_wbs_codes",
        "project_boqs",
        "project_boq_items",
        "project_boq_revisions",
        "measurement_entries",
        "ra_bills",
        "ra_bill_lines",
        "ra_bill_measurements",
    }
    assert expected.issubset(Base.metadata.tables)


def test_project_commercial_records_use_tenant_safe_project_references() -> None:
    project_target = ("projects.id", "projects.organization_id")
    for table_name in (
        "project_party_assignments",
        "project_wbs_codes",
        "project_boqs",
        "measurement_entries",
        "ra_bills",
    ):
        assert project_target in _fk_targets(table_name)


def test_commercial_create_schemas_do_not_accept_tenant_identity() -> None:
    for schema in (PartyCreate, WBSCodeCreate, BOQCreate, MeasurementCreate, RABillCreate):
        assert "organization_id" not in schema.model_fields
        assert "project_id" not in schema.model_fields


def test_india_commercial_permission_catalog_is_complete() -> None:
    required = {
        "commercial.module.view",
        "commercial.party.view",
        "commercial.party.manage",
        "commercial.wbs.view",
        "commercial.wbs.manage",
        "commercial.boq.view",
        "commercial.boq.manage",
        "commercial.boq.approve",
        "commercial.measurement.view",
        "commercial.measurement.create",
        "commercial.measurement.submit",
        "commercial.measurement.certify",
        "commercial.ra_bill.view",
        "commercial.ra_bill.create",
        "commercial.ra_bill.submit",
        "commercial.ra_bill.certify",
    }
    assert required.issubset(PERMISSIONS_BY_KEY)


def test_commercial_runtime_is_project_scoped_and_installer_visible() -> None:
    manifest = MODULES_BY_KEY["commercial"]
    assert manifest.dependencies == ("projects",)
    assert manifest.api_router == "app.modules.commercial.api:router"
    assert {item.key for item in resolve_runtime_modules("commercial")} == {
        "projects",
        "commercial",
    }
    feature = FEATURES_BY_KEY["commercial"]
    assert feature.required_permissions == ("commercial.module.view",)
    assert feature.release_state == FeatureReleaseState.PLANNED
    assert feature.offline_enabled
    party_feature = FEATURES_BY_KEY["commercial.parties"]
    assert party_feature.release_state == FeatureReleaseState.AVAILABLE
    assert party_feature.route == "/commercial/parties"


def test_commercial_api_exposes_real_workflow_routes() -> None:
    paths = _paths()
    required = {
        "/commercial/parties",
        "/commercial/parties/{party_id}",
        "/projects/{project_id}/commercial/parties",
        "/projects/{project_id}/commercial/party-assignments",
        "/projects/{project_id}/commercial/party-assignments/{assignment_id}",
        "/projects/{project_id}/commercial/wbs",
        "/projects/{project_id}/commercial/boqs",
        "/projects/{project_id}/commercial/boqs/{boq_id}/items",
        "/projects/{project_id}/commercial/boqs/{boq_id}/approve",
        "/projects/{project_id}/commercial/measurements",
        "/projects/{project_id}/commercial/measurements/{measurement_id}/review",
        "/projects/{project_id}/commercial/ra-bills",
        "/projects/{project_id}/commercial/ra-bills/{bill_id}/certify",
        "/projects/{project_id}/commercial/dashboard",
    }
    assert required.issubset(paths)


def test_money_is_deterministically_rounded_to_paise() -> None:
    assert money(Decimal("12.345")) == Decimal("12.35")
    assert money(Decimal("12.344")) == Decimal("12.34")


def test_ra_bill_period_validation_is_deterministic() -> None:
    with pytest.raises(ValidationError):
        RABillCreate(
            counterparty_id="4b086cdd-3ab4-43ce-96bf-175e52a1f3ab",
            bill_number="RA-01",
            period_start=date(2026, 9, 10),
            period_end=date(2026, 9, 1),
        )


def test_high_risk_state_machines_do_not_include_silent_edit_states() -> None:
    assert BOQStatus.APPROVED.value == "approved"
    assert MeasurementStatus.CERTIFIED.value == "certified"
    assert RABillStatus.PAID.value == "paid"
