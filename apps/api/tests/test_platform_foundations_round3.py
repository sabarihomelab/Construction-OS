from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.contracts import ContractCompatibilityError, ContractRegistry, ContractSpec
from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authentication.providers import AuthenticationAssertion
from app.modules.authentication.service import AuthenticationValidationError, validate_assertion
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.help.models import TenantKnowledgeSource
from app.modules.help.service import ProductHelpRegistry, ProductHelpTopic, knowledge_source_is_visible
from app.modules.integrations.mapping_service import MappingValidationError, validate_mapping_spec
from app.modules.sessions.models import AuthenticationLevel, AuthenticationMethod


def test_governance_help_and_mapping_tables_are_registered() -> None:
    expected = {
        "data_lifecycle_policies",
        "data_lifecycle_policy_versions",
        "legal_holds",
        "lifecycle_runs",
        "tenant_knowledge_sources",
        "tenant_knowledge_chunks",
        "mapping_profiles",
        "mapping_profile_versions",
        "sync_checkpoints",
        "integration_conflicts",
    }
    assert expected.issubset(Base.metadata.tables)


def test_governance_and_help_permissions_are_in_runtime_catalog() -> None:
    expected = {
        "data.governance.view",
        "data.governance.manage",
        "data.lifecycle.execute",
        "help.content.view",
        "help.knowledge.manage",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)


def test_contract_registry_rejects_unsupported_version() -> None:
    registry = ContractRegistry()
    registry.register(ContractSpec(key="test.contract", current_version=3, minimum_supported_version=2))
    registry.get("test.contract").require_supported(2)
    registry.get("test.contract").require_supported(3)
    with pytest.raises(ContractCompatibilityError):
        registry.get("test.contract").require_supported(1)
    with pytest.raises(ContractCompatibilityError):
        registry.get("test.contract").require_supported(4)


def test_authentication_assertion_requires_timezone_aware_timestamp() -> None:
    assertion = AuthenticationAssertion(
        provider_key="oidc",
        subject="user-123",
        email="user@example.com",
        email_verified=True,
        display_name="User",
        method=AuthenticationMethod.OIDC,
        level=AuthenticationLevel.MFA,
        authenticated_at=datetime(2026, 9, 10, 10, 0),
    )
    with pytest.raises(AuthenticationValidationError):
        validate_assertion(assertion)


def test_authentication_assertion_accepts_verified_time_context() -> None:
    assertion = AuthenticationAssertion(
        provider_key="oidc",
        subject="user-123",
        email="user@example.com",
        email_verified=True,
        display_name="User",
        method=AuthenticationMethod.OIDC,
        level=AuthenticationLevel.MFA,
        authenticated_at=datetime(2026, 9, 10, 5, 0, tzinfo=UTC),
        mfa_verified_at=datetime(2026, 9, 10, 5, 0, tzinfo=UTC),
    )
    validate_assertion(assertion, now=datetime(2026, 9, 10, 6, 0, tzinfo=UTC))


def test_help_route_registry_respects_permission() -> None:
    registry = ProductHelpRegistry()
    registry.register(
        ProductHelpTopic(
            key="finance.budget",
            title="Budget Help",
            route_prefix="/finance/budget",
            document_path="docs/help/finance/budget.md",
            required_permission_key="finance.budget.view",
        )
    )
    assert registry.for_route("/finance/budget/1", set()) == ()
    assert len(registry.for_route("/finance/budget/1", {"finance.budget.view"})) == 1


def test_tenant_knowledge_scope_defaults_to_deny() -> None:
    source = TenantKnowledgeSource(
        organization_id=uuid4(),
        key="project-specs",
        name="Project Specifications",
        kind="file",
        status="ready",
        source_version=1,
        required_permission_key="projects.project.view",
        scope_type="project",
        scope_id="project-123",
        configuration={},
    )
    assert not knowledge_source_is_visible(source, permission_keys={"projects.project.view"})
    assert knowledge_source_is_visible(
        source,
        permission_keys={"projects.project.view"},
        allowed_scopes={"project": {"project-123"}},
    )


def test_mapping_spec_rejects_duplicate_target_field() -> None:
    with pytest.raises(MappingValidationError):
        validate_mapping_spec(
            {
                "fields": [
                    {"source": "external_name", "target": "name"},
                    {"source": "external_title", "target": "name"},
                ]
            }
        )


def test_checkpoint_and_conflict_tables_preserve_revision_and_both_sides() -> None:
    checkpoint = Base.metadata.tables["sync_checkpoints"]
    conflict = Base.metadata.tables["integration_conflicts"]
    assert "revision" in checkpoint.c
    assert "cursor" in checkpoint.c
    assert "source_values" in conflict.c
    assert "internal_values" in conflict.c
    assert "resolution" in conflict.c
