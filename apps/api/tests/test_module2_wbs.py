from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.modules.commercial.api import router as commercial_router
from app.modules.commercial.models import RecordStatus, WBSCode, WBSKind
from app.modules.commercial.wbs_schemas import WBSCodeCreate, WBSCodeUpdate
from app.modules.commercial.wbs_service import flatten_wbs_tree
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.features.service import resolve_visible_features


def _commercial_paths() -> dict[str, dict[str, object]]:
    application = FastAPI()
    application.include_router(commercial_router, prefix="/api/v1")
    return application.openapi()["paths"]


def test_wbs_feature_is_available_without_releasing_all_commercial() -> None:
    feature = FEATURES_BY_KEY["commercial.wbs"]
    commercial = FEATURES_BY_KEY["commercial"]

    assert feature.route == "/commercial/wbs"
    assert feature.required_permissions == ("commercial.wbs.view",)
    assert feature.release_state == FeatureReleaseState.AVAILABLE
    assert commercial.release_state == FeatureReleaseState.PLANNED


def test_wbs_feature_requires_commercial_runtime_module() -> None:
    permission = {"commercial.wbs.view"}

    visible = resolve_visible_features(permission, deployment_modules={"commercial", "projects"})
    assert "commercial.wbs" in {feature.key for feature in visible}

    hidden = resolve_visible_features(permission, deployment_modules={"projects"})
    assert "commercial.wbs" not in {feature.key for feature in hidden}


def test_wbs_api_exposes_complete_non_destructive_surface() -> None:
    paths = _commercial_paths()
    required = {
        "/api/v1/projects/{project_id}/commercial/wbs",
        "/api/v1/projects/{project_id}/commercial/wbs/tree",
        "/api/v1/projects/{project_id}/commercial/wbs/{wbs_id}",
    }
    assert required.issubset(paths)
    assert set(paths["/api/v1/projects/{project_id}/commercial/wbs"]) >= {"get", "post"}
    assert set(paths["/api/v1/projects/{project_id}/commercial/wbs/{wbs_id}"]) >= {
        "get",
        "patch",
    }
    assert "delete" not in paths["/api/v1/projects/{project_id}/commercial/wbs/{wbs_id}"]


def test_wbs_client_schema_does_not_accept_tenant_identity() -> None:
    with pytest.raises(ValidationError):
        WBSCodeCreate.model_validate(
            {
                "organization_id": str(uuid4()),
                "project_id": str(uuid4()),
                "code": "civ",
                "name": "Civil",
                "kind": "trade",
            }
        )


def test_wbs_partial_update_does_not_implicitly_clear_parent() -> None:
    payload = WBSCodeUpdate(expected_revision=3, name="Concrete")
    assert "parent_id" not in payload.model_fields_set
    assert payload.model_dump(exclude_unset=True) == {
        "expected_revision": 3,
        "name": "Concrete",
    }


def test_flatten_wbs_tree_preserves_hierarchy_and_code_order() -> None:
    project_id = uuid4()
    organization_id = uuid4()
    root_a = WBSCode(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        parent_id=None,
        code="01",
        name="Civil",
        kind=WBSKind.TRADE,
        status=RecordStatus.ACTIVE,
        revision=1,
    )
    root_b = WBSCode(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        parent_id=None,
        code="02",
        name="MEP",
        kind=WBSKind.TRADE,
        status=RecordStatus.ACTIVE,
        revision=1,
    )
    child = WBSCode(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        parent_id=root_a.id,
        code="01.10",
        name="Concrete",
        kind=WBSKind.COST_CODE,
        status=RecordStatus.ACTIVE,
        revision=1,
    )

    flattened = flatten_wbs_tree([root_b, child, root_a])

    assert [(row.code, depth) for row, depth, _, _ in flattened] == [
        ("01", 0),
        ("01.10", 1),
        ("02", 0),
    ]
    assert flattened[0][3] == 1
    assert flattened[1][2] == ("01", "01.10")
