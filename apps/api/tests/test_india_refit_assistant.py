from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.help.assistant import (
    AssistantEvidence,
    AssistantMode,
    build_prompt,
    retrieve_product_evidence,
)
from app.modules.organizations.models import (
    INDIA_DEFAULT_CURRENCY,
    INDIA_DEFAULT_LOCALE,
    INDIA_DEFAULT_TIMEZONE,
    OrganizationSettings,
    UnitSystem,
)
from app.modules.organizations.schemas import OrganizationCreate, OrganizationSettingsCreate


def test_new_company_defaults_are_india_first() -> None:
    company = OrganizationCreate(name="ABC Civil Contractors", slug="abc-civil")
    settings = OrganizationSettingsCreate()

    assert company.country_code == "IN"
    assert settings.locale == "en-IN" == INDIA_DEFAULT_LOCALE
    assert settings.timezone == "Asia/Kolkata" == INDIA_DEFAULT_TIMEZONE
    assert settings.base_currency == "INR" == INDIA_DEFAULT_CURRENCY
    assert settings.unit_system == UnitSystem.METRIC


def test_orm_defaults_are_india_first_without_rewriting_existing_rows() -> None:
    columns = OrganizationSettings.__table__.columns
    assert columns.locale.default.arg == "en-IN"
    assert columns.timezone.default.arg == "Asia/Kolkata"
    assert columns.base_currency.default.arg == "INR"


def test_environment_market_is_locked_to_india_for_current_release() -> None:
    settings = Settings()
    assert settings.product_market == "IN"
    with pytest.raises(ValidationError):
        Settings(product_market="US")


def test_assistant_is_disabled_by_default_and_provider_config_is_validated() -> None:
    settings = Settings()
    assert not settings.ai_assistant_enabled
    assert settings.ai_provider == "disabled"

    with pytest.raises(ValidationError):
        Settings(ai_assistant_enabled=True, ai_provider="disabled")

    configured = Settings(
        ai_assistant_enabled=True,
        ai_provider="ollama",
        ai_base_url="http://127.0.0.1:11434",
        ai_model="example-model",
    )
    assert configured.ai_assistant_enabled


def test_assistant_permissions_and_feature_are_explicit() -> None:
    assert "help.assistant.use" in PERMISSIONS_BY_KEY
    assert "help.assistant.upgrade" in PERMISSIONS_BY_KEY

    feature = FEATURES_BY_KEY["help.assistant"]
    assert feature.parent_key == "help"
    assert feature.required_permissions == ("help.assistant.use",)
    assert feature.release_state == FeatureReleaseState.PLANNED


def test_assistant_prompt_preserves_non_authoritative_boundary() -> None:
    evidence = [
        AssistantEvidence(
            source_id="product:test:0",
            kind="product",
            title="Test",
            content="A verified database backup is required before migration.",
        )
    ]
    messages = build_prompt("Can you upgrade this installation?", AssistantMode.UPGRADE, evidence)
    system = messages[0]["content"]

    assert "only from the evidence supplied" in system
    assert "Never claim that you executed an upgrade" in system
    assert "Never invent current GST" in system
    assert "RA billing" in system


def test_india_product_knowledge_is_retrievable() -> None:
    evidence = retrieve_product_evidence(
        "How should BOQ, measurement and RA billing work for an Indian contractor?",
        mode=AssistantMode.HELP,
    )
    assert evidence
    assert any(item.source_id.startswith("product:india-") for item in evidence)


def test_assistant_api_is_mounted_without_enabling_model_inference() -> None:
    paths = set(create_app().openapi()["paths"])
    assert "/api/v1/help/assistant/capabilities" in paths
    assert "/api/v1/help/assistant/query" in paths


def test_repository_contains_india_first_contract() -> None:
    root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "VERSION").is_file()
    )
    contract = (root / "docs/product/INDIA-FIRST-PRODUCT-CONTRACT.md").read_text(
        encoding="utf-8"
    )
    assert "India-first" in contract
    assert "TallyPrime" in contract
    assert "RA Billing" in contract
