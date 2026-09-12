from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.deployment.router import DeploymentBootstrapResponse, router as deployment_router


def test_production_requires_company_bound_deployment() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            deployment_id="customer-prod-1",
            deployment_organization_id=None,
        )


def test_production_accepts_explicit_company_binding() -> None:
    organization_id = uuid4()
    settings = Settings(
        _env_file=None,
        environment="production",
        deployment_id="customer-prod-1",
        deployment_organization_id=organization_id,
    )
    assert settings.deployment_organization_id == organization_id


def test_deployment_bootstrap_is_versioned_and_secret_free() -> None:
    paths = {f"/api/v1{route.path}" for route in deployment_router.routes}
    assert "/api/v1/deployment/bootstrap" in paths
    assert {
        "deployment_id",
        "dedicated_company",
        "organization",
        "environment",
        "environment_name",
        "api_path",
    } == set(DeploymentBootstrapResponse.model_fields)
