from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.equipment.router import router as equipment_router
from app.modules.equipment.schemas import EquipmentAssignmentCreate, MaterialDeliveryCreate
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.meetings.router import router as meetings_router
from app.modules.meetings.schemas import MeetingCreate
from app.modules.safety.router import router as safety_router
from app.modules.safety.schemas import SafetyRecordCreate
from app.modules.search.bootstrap import register_builtin_search_providers
from app.modules.search.providers import search_projection_providers
from app.runtime.modules import MODULES_BY_KEY, resolve_runtime_modules


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def _paths(router) -> set[str]:
    return {route.path for route in router.routes if hasattr(route, "path")}


def test_site_operations_and_meetings_tables_are_registered() -> None:
    expected = {
        "safety_records",
        "safety_corrective_actions",
        "inspection_templates",
        "inspection_template_versions",
        "inspection_runs",
        "inspection_results",
        "punch_items",
        "equipment_assets",
        "project_equipment_assignments",
        "equipment_maintenance",
        "materials",
        "project_material_plans",
        "material_deliveries",
        "meeting_series",
        "meetings",
        "meeting_attendees",
        "meeting_agenda_items",
        "meeting_action_items",
        "meeting_references",
        "meeting_history_events",
    }
    assert expected.issubset(Base.metadata.tables)


def test_project_scoped_records_have_tenant_safe_project_references() -> None:
    project_target = ("projects.id", "projects.organization_id")
    for table_name in (
        "safety_records",
        "inspection_runs",
        "punch_items",
        "project_equipment_assignments",
        "project_material_plans",
        "material_deliveries",
        "meetings",
    ):
        assert project_target in _fk_targets(table_name)


def test_project_scoped_create_schemas_do_not_accept_tenant_identity() -> None:
    for schema in (
        SafetyRecordCreate,
        EquipmentAssignmentCreate,
        MaterialDeliveryCreate,
        MeetingCreate,
    ):
        assert "organization_id" not in schema.model_fields
        assert "project_id" not in schema.model_fields


def test_new_module_permissions_are_in_effective_permission_catalog() -> None:
    required = {
        "safety.module.view",
        "safety.record.view",
        "safety.inspection.execute",
        "safety.punch.close",
        "equipment.module.view",
        "equipment.asset.manage",
        "materials.delivery.manage",
        "meetings.meeting.view",
        "meetings.minutes.finalize",
        "meetings.action.manage",
    }
    assert required.issubset(PERMISSIONS_BY_KEY)


def test_new_features_are_installer_visible_but_not_released_ui() -> None:
    for feature_key in ("safety", "equipment", "meetings"):
        feature = FEATURES_BY_KEY[feature_key]
        assert feature.release_state == FeatureReleaseState.PLANNED
        assert feature.offline_enabled

    assert FEATURES_BY_KEY["safety"].required_permissions == ("safety.module.view",)
    assert FEATURES_BY_KEY["equipment"].required_permissions == ("equipment.module.view",)
    assert FEATURES_BY_KEY["meetings"].required_permissions == ("meetings.meeting.view",)


def test_runtime_manifests_keep_optional_integrations_optional() -> None:
    assert MODULES_BY_KEY["safety"].dependencies == ("projects",)
    assert MODULES_BY_KEY["equipment"].dependencies == ("projects",)
    assert MODULES_BY_KEY["meetings"].dependencies == ("projects",)

    assert {item.key for item in resolve_runtime_modules("safety")} == {"projects", "safety"}
    assert {item.key for item in resolve_runtime_modules("equipment")} == {"projects", "equipment"}
    assert {item.key for item in resolve_runtime_modules("meetings")} == {"projects", "meetings"}


def test_builtin_search_bootstrap_registers_new_projection_types() -> None:
    register_builtin_search_providers()
    required = {
        "safety_record",
        "inspection_run",
        "punch_item",
        "equipment_asset",
        "material",
        "material_delivery",
        "meeting",
        "meeting_action_item",
        "worker",
        "timecard",
    }
    assert required.issubset(search_projection_providers.registered_entity_types())


def test_site_operations_and_meetings_router_contracts_are_mounted_at_module_level() -> None:
    safety_paths = _paths(safety_router)
    equipment_paths = _paths(equipment_router)
    meeting_paths = _paths(meetings_router)

    assert "/safety/inspection-templates" in safety_paths
    assert "/projects/{project_id}/safety/records" in safety_paths
    assert "/projects/{project_id}/punch" in safety_paths

    assert "/equipment/assets" in equipment_paths
    assert "/materials" in equipment_paths
    assert "/projects/{project_id}/materials/deliveries" in equipment_paths

    assert "/projects/{project_id}/meetings" in meeting_paths
    assert "/projects/{project_id}/meetings/{meeting_id}/minutes" in meeting_paths
    assert "/projects/{project_id}/meetings/{meeting_id}/actions" in meeting_paths
