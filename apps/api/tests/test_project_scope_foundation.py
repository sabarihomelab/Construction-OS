from uuid import uuid4

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.events.models import OutboxEvent
from app.modules.events.service import event_is_visible
from app.modules.projects.access import (
    effective_project_permissions,
    visible_project_scope,
)
from app.modules.projects.schemas import ProjectCreate


def test_project_scope_tables_are_registered() -> None:
    assert {
        "projects",
        "project_memberships",
        "project_role_assignments",
    }.issubset(Base.metadata.tables)


def test_project_capabilities_are_in_runtime_catalog() -> None:
    assert {
        "projects.project.view",
        "projects.project.create",
        "projects.project.update",
        "projects.project.archive",
        "projects.membership.view",
        "projects.membership.manage",
    }.issubset(PERMISSIONS_BY_KEY)


def test_project_create_never_accepts_tenant_identity() -> None:
    assert "organization_id" not in ProjectCreate.model_fields


def test_company_project_view_creates_all_project_scope() -> None:
    assert visible_project_scope({"projects.project.view"}, {}) == {"*"}


def test_project_role_only_exposes_projects_with_view_permission() -> None:
    permissions = {
        "project-a": {"projects.project.view", "field.daily_log.view"},
        "project-b": {"finance.budget.view"},
    }
    assert visible_project_scope(set(), permissions) == {"project-a"}


def test_effective_permissions_merge_company_and_one_project_only() -> None:
    permissions = {
        "project-a": {"finance.budget.view"},
        "project-b": {"field.daily_log.view"},
    }
    effective = effective_project_permissions(
        project_id="project-a",
        organization_permissions={"projects.project.view"},
        project_permissions=permissions,
    )
    assert effective == {"projects.project.view", "finance.budget.view"}
    assert "field.daily_log.view" not in effective


def test_realtime_scoped_permission_does_not_leak_to_another_project() -> None:
    organization_id = uuid4()
    event_a = OutboxEvent(
        organization_id=organization_id,
        event_type="budget.updated",
        entity_type="budget",
        entity_id="budget-a",
        required_permission_key="finance.budget.view",
        scope_type="project",
        scope_id="project-a",
        payload={},
    )
    event_b = OutboxEvent(
        organization_id=organization_id,
        event_type="budget.updated",
        entity_type="budget",
        entity_id="budget-b",
        required_permission_key="finance.budget.view",
        scope_type="project",
        scope_id="project-b",
        payload={},
    )
    scoped_permissions = {
        "project": {
            "project-a": {"finance.budget.view"},
            "project-b": {"projects.project.view"},
        }
    }
    allowed_scopes = {"project": {"project-a", "project-b"}}

    assert event_is_visible(
        event_a,
        set(),
        allowed_scopes=allowed_scopes,
        scoped_permissions=scoped_permissions,
    )
    assert not event_is_visible(
        event_b,
        set(),
        allowed_scopes=allowed_scopes,
        scoped_permissions=scoped_permissions,
    )


def test_project_foreign_keys_are_tenant_consistent() -> None:
    project_memberships = Base.metadata.tables["project_memberships"]
    role_assignments = Base.metadata.tables["project_role_assignments"]

    membership_fk_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in project_memberships.foreign_key_constraints
    }
    role_fk_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in role_assignments.foreign_key_constraints
    }

    assert ("projects.id", "projects.organization_id") in membership_fk_targets
    assert (
        "organization_memberships.id",
        "organization_memberships.organization_id",
    ) in membership_fk_targets
    assert (
        "project_memberships.id",
        "project_memberships.organization_id",
    ) in role_fk_targets
    assert ("roles.id", "roles.organization_id") in role_fk_targets
