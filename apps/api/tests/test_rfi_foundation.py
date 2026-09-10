from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.main import app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.rfis.models import RFIReferenceType, RFIStatus
from app.modules.rfis.search import rfi_search_projection
from app.modules.search.providers import search_projection_providers


def _constraint_names(table_name: str) -> set[str | None]:
    return {constraint.name for constraint in Base.metadata.tables[table_name].constraints}


def test_rfi_tables_are_registered() -> None:
    expected = {
        "rfi_project_counters",
        "rfis",
        "rfi_responses",
        "rfi_references",
        "rfi_history_events",
    }
    assert expected.issubset(Base.metadata.tables)


def test_rfi_permissions_are_registered() -> None:
    expected = {
        "rfis.rfi.view",
        "rfis.rfi.create",
        "rfis.rfi.update",
        "rfis.rfi.respond",
        "rfis.rfi.close",
        "rfis.rfi.manage",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)


def test_rfi_feature_stays_hidden_until_release_ui_is_ready() -> None:
    feature = FEATURES_BY_KEY["rfis"]
    assert feature.release_state == FeatureReleaseState.PLANNED
    assert feature.offline_enabled
    assert feature.required_permissions == ("rfis.rfi.view",)


def test_rfi_responsibility_is_database_scoped_to_project_membership() -> None:
    assert "uq_project_memberships_project_member_org" in _constraint_names(
        "project_memberships"
    )
    assert "fk_rfis_ball_in_court_project_member_org" in _constraint_names("rfis")


def test_rfi_number_and_response_sequences_are_unique_per_parent() -> None:
    assert "uq_rfis_project_number" in _constraint_names("rfis")
    assert "uq_rfi_responses_rfi_sequence" in _constraint_names("rfi_responses")
    assert "uq_rfi_project_counters_project" in _constraint_names("rfi_project_counters")


def test_rfi_reference_types_are_ready_for_cross_module_links() -> None:
    assert RFIReferenceType.DRAWING_REVISION.value == "drawing_revision"
    assert RFIReferenceType.SPECIFICATION_SECTION.value == "specification_section"
    assert RFIReferenceType.SCHEDULE_ACTIVITY.value == "schedule_activity"
    assert RFIReferenceType.CHANGE_EVENT.value == "change_event"


def test_rfi_lifecycle_has_non_destructive_terminal_states() -> None:
    assert RFIStatus.CLOSED.value == "closed"
    assert RFIStatus.VOID.value == "void"


def test_rfi_search_provider_is_project_scoped_and_registered() -> None:
    assert search_projection_providers.get("rfi") is rfi_search_projection


def test_rfi_router_is_mounted_under_versioned_project_api() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/rfis" in paths
    assert "/api/v1/projects/{project_id}/rfis/{rfi_id}/responses" in paths
    assert "/api/v1/projects/{project_id}/rfis/{rfi_id}/history" in paths
