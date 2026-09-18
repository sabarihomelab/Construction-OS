from app.main import app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.authorization.templates import INDIA_ROLE_TEMPLATES, ROLE_TEMPLATES_BY_KEY
from app.modules.identity.models import MembershipKind


def test_india_role_templates_have_unique_keys_and_known_permissions() -> None:
    assert len(ROLE_TEMPLATES_BY_KEY) == len(INDIA_ROLE_TEMPLATES)
    assert len(INDIA_ROLE_TEMPLATES) >= 12

    known_permissions = set(PERMISSIONS_BY_KEY)
    for template in INDIA_ROLE_TEMPLATES:
        assert template.permission_keys
        assert template.permission_keys <= known_permissions


def test_field_roles_do_not_receive_commercial_or_financial_authority() -> None:
    forbidden = {
        "commercial.boq.view",
        "commercial.boq.manage",
        "commercial.boq.approve",
        "commercial.measurement.certify",
        "commercial.ra_bill.view",
        "commercial.ra_bill.certify",
        "finance.budget.view",
        "financials.module.view",
        "workforce.rate.view",
        "equipment.rate.view",
    }
    for key in ("site-engineer", "site-supervisor", "labour-contractor-supervisor"):
        assert ROLE_TEMPLATES_BY_KEY[key].permission_keys.isdisjoint(forbidden)


def test_external_role_templates_are_marked_external() -> None:
    for key in (
        "client-pmc-reviewer",
        "consultant-engineer",
        "subcontractor-engineer",
        "labour-contractor-supervisor",
    ):
        assert ROLE_TEMPLATES_BY_KEY[key].membership_kind_hint == MembershipKind.EXTERNAL


def test_role_templates_expose_safe_assignment_scope_hints() -> None:
    assert ROLE_TEMPLATES_BY_KEY["company-management"].scope_hint == "company"
    for key in ("project-manager", "site-engineer", "site-supervisor"):
        assert ROLE_TEMPLATES_BY_KEY[key].scope_hint == "project"


def test_access_management_routes_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/security/permissions" in paths
    assert "/api/v1/security/role-templates" in paths
    assert "/api/v1/security/roles" in paths
    assert "/api/v1/security/memberships" in paths
    assert "/api/v1/security/party-references" in paths
    assert "/api/v1/security/memberships/{membership_id}/party-affiliation" in paths
    assert "/api/v1/projects/{project_id}/access" in paths
    assert "/api/v1/projects/{project_id}/memberships/{project_membership_id}/roles" in paths
