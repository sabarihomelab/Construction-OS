import csv
import io
from decimal import Decimal

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.modules.commercial.api import router as commercial_router
from app.modules.commercial.boq_schemas import (
    BOQCreate,
    BOQImportApplyRequest,
    BOQItemCreate,
    BOQItemUpdate,
    BOQUpdate,
)
from app.modules.commercial.boq_service import CSV_FIELDS, boq_csv_template, money
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.features.service import resolve_visible_features


def _commercial_paths() -> dict[str, dict[str, object]]:
    application = FastAPI()
    application.include_router(commercial_router, prefix="/api/v1")
    return application.openapi()["paths"]


def test_boq_feature_is_available_without_releasing_all_commercial() -> None:
    feature = FEATURES_BY_KEY["commercial.boq"]
    commercial = FEATURES_BY_KEY["commercial"]

    assert feature.route == "/commercial/boq"
    assert feature.required_permissions == ("commercial.boq.view",)
    assert feature.release_state == FeatureReleaseState.AVAILABLE
    assert commercial.release_state == FeatureReleaseState.PLANNED


def test_boq_feature_requires_commercial_runtime_module() -> None:
    permission = {"commercial.boq.view"}

    visible = resolve_visible_features(permission, deployment_modules={"commercial", "projects"})
    assert "commercial.boq" in {feature.key for feature in visible}

    hidden = resolve_visible_features(permission, deployment_modules={"projects"})
    assert "commercial.boq" not in {feature.key for feature in hidden}


def test_boq_api_exposes_complete_governed_surface() -> None:
    paths = _commercial_paths()
    root = "/api/v1/projects/{project_id}/commercial/boqs"
    detail = "/api/v1/projects/{project_id}/commercial/boqs/{boq_id}"
    item = "/api/v1/projects/{project_id}/commercial/boqs/{boq_id}/items/{item_id}"

    assert set(paths[root]) >= {"get", "post"}
    assert set(paths[detail]) >= {"get", "patch"}
    assert "delete" not in paths[detail]
    assert set(paths[item]) >= {"patch", "delete"}
    assert f"{detail}/approve" in paths
    assert f"{detail}/cancel" in paths
    assert f"{detail}/revisions" in paths
    assert f"{detail}/import/preview" in paths
    assert f"{detail}/import/apply" in paths
    assert f"{detail}/export.csv" in paths
    assert f"{detail}/revisions/{{version_number}}/export.csv" in paths
    assert f"{root}/template.csv" in paths


def test_boq_client_schemas_do_not_expose_tenant_identity() -> None:
    for schema in (BOQCreate, BOQUpdate, BOQItemCreate, BOQItemUpdate):
        assert "organization_id" not in schema.model_fields
        assert "project_id" not in schema.model_fields


def test_boq_partial_item_update_does_not_implicitly_clear_wbs() -> None:
    payload = BOQItemUpdate(expected_revision=3, expected_boq_revision=9, description="Concrete")

    assert "wbs_code_id" not in payload.model_fields_set
    assert payload.model_dump(exclude_unset=True) == {
        "expected_revision": 3,
        "expected_boq_revision": 9,
        "description": "Concrete",
    }


def test_boq_import_apply_requires_parent_revision() -> None:
    with pytest.raises(ValidationError):
        BOQImportApplyRequest.model_validate({"csv_text": "line_number,item_code\n1,A"})


def test_boq_quantity_precision_is_not_silently_rounded() -> None:
    with pytest.raises(ValidationError):
        BOQItemCreate.model_validate(
            {
                "line_number": 1,
                "item_code": "CIV-001",
                "description": "Concrete",
                "unit_code": "M3",
                "quantity": "1.0009",
                "rate": "100.00",
            }
        )


def test_boq_currency_is_normalized_and_money_rounding_is_centralized() -> None:
    payload = BOQCreate(code="boq-1", name="Main BOQ", currency_code="inr")

    assert payload.currency_code == "INR"
    assert money(Decimal("12.345")) == Decimal("12.35")


def test_boq_csv_template_matches_supported_import_contract() -> None:
    reader = csv.DictReader(io.StringIO(boq_csv_template()))

    assert tuple(reader.fieldnames or ()) == CSV_FIELDS
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["line_number"] == "1"
    assert rows[0]["item_code"] == "CIV-CONC-001"
