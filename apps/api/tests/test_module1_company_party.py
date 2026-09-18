from datetime import UTC, datetime

from app.main import create_app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.commercial.schemas import ProjectPartyAssignmentUpdate
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.organizations.models import (
    INDIA_DEFAULT_CURRENCY,
    INDIA_DEFAULT_LOCALE,
    INDIA_DEFAULT_TIMEZONE,
    UnitSystem,
)
from app.modules.organizations.schemas import OrganizationCreate, OrganizationSettingsCreate


def test_new_company_schema_uses_india_preset() -> None:
    company = OrganizationCreate(name="Acme Construction", slug="acme-construction")
    settings = OrganizationSettingsCreate()

    assert company.country_code == "IN"
    assert settings.locale == INDIA_DEFAULT_LOCALE == "en-IN"
    assert settings.timezone == INDIA_DEFAULT_TIMEZONE == "Asia/Kolkata"
    assert settings.base_currency == INDIA_DEFAULT_CURRENCY == "INR"
    assert settings.unit_system == UnitSystem.METRIC


def test_company_and_party_pages_are_available_without_marking_all_commercial_complete() -> None:
    company = FEATURES_BY_KEY["admin.company"]
    parties = FEATURES_BY_KEY["commercial.parties"]
    commercial = FEATURES_BY_KEY["commercial"]

    assert company.route == "/admin/company"
    assert company.release_state == FeatureReleaseState.AVAILABLE
    assert parties.route == "/commercial/parties"
    assert parties.release_state == FeatureReleaseState.AVAILABLE
    assert commercial.release_state == FeatureReleaseState.PLANNED


def test_company_settings_reuse_existing_high_risk_admin_permission() -> None:
    assert "admin.settings.view" in PERMISSIONS_BY_KEY
    assert "admin.configuration.manage" in PERMISSIONS_BY_KEY


def test_project_party_lifecycle_requires_concurrency_token() -> None:
    expected = datetime.now(UTC)
    payload = ProjectPartyAssignmentUpdate(expected_updated_at=expected, active=False)
    assert payload.expected_updated_at == expected
    assert payload.active is False


def test_live_api_mounts_module1_routes_and_not_old_public_company_crud() -> None:
    application = create_app()
    paths = set(application.openapi()["paths"])

    assert "/api/v1/organization" in paths
    assert "/api/v1/organization/settings" in paths
    assert "/api/v1/commercial/parties/{party_id}" in paths
    assert "/api/v1/projects/{project_id}/commercial/party-assignments" in paths
    assert "/api/v1/projects/{project_id}/commercial/party-assignments/{assignment_id}" in paths
    assert "/api/v1/organizations" not in paths
