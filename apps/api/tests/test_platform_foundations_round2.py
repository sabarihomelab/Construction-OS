import pytest

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.exports.service import ExportChunk, ExportValidationError, validate_export_chunk
from app.modules.integrations.service import (
    IntegrationValidationError,
    canonical_external_payload,
)
from app.modules.reporting.service import (
    DatasetContract,
    DatasetField,
    ReportingValidationError,
    validate_standard_query_spec,
)


def test_remaining_platform_tables_are_registered() -> None:
    expected = {
        "configuration_templates",
        "configuration_template_versions",
        "setup_runs",
        "configuration_health_checks",
        "data_export_requests",
        "data_export_manifest_items",
        "integration_connectors",
        "ingestion_batches",
        "staged_external_records",
        "external_record_mappings",
        "saved_views",
        "report_definitions",
        "report_definition_versions",
        "report_runs",
        "dashboard_definitions",
        "operational_health_snapshots",
        "operational_events",
        "operations_retention_policies",
    }
    assert expected.issubset(Base.metadata.tables)


def test_export_manifest_rejects_path_traversal() -> None:
    chunk = ExportChunk(
        module_key="projects",
        entity_type="project",
        relative_path="../secrets.json",
        schema_version=1,
        record_count=1,
    )
    with pytest.raises(ExportValidationError):
        validate_export_chunk(chunk)


def test_external_staging_redacts_secret_like_fields_and_hashes_canonical_payload() -> None:
    left, left_hash = canonical_external_payload(
        {"external_id": "A1", "access_token": "hidden", "value": 10}
    )
    right, right_hash = canonical_external_payload(
        {"value": 10, "access_token": "different", "external_id": "A1"}
    )
    assert left["access_token"] == "[REDACTED]"
    assert right["access_token"] == "[REDACTED]"
    assert left_hash == right_hash


def test_external_staging_rejects_oversized_payload() -> None:
    with pytest.raises(IntegrationValidationError):
        canonical_external_payload({"text": "x" * (257 * 1024)})


def test_reporting_query_can_only_use_contract_fields() -> None:
    contract = DatasetContract(
        key="projects.summary",
        fields=(
            DatasetField(key="project_name", data_type="text"),
            DatasetField(key="budget", data_type="currency", filterable=False),
        ),
        required_permission_key="projects.project.view",
    )
    validate_standard_query_spec({"fields": ["project_name"]}, contract)
    with pytest.raises(ReportingValidationError):
        validate_standard_query_spec({"fields": ["secret_column"]}, contract)
    with pytest.raises(ReportingValidationError):
        validate_standard_query_spec(
            {"fields": ["project_name"], "filters": [{"field": "budget", "op": "gt", "value": 0}]},
            contract,
        )


def test_report_run_output_is_managed_file_reference_not_blob() -> None:
    table = Base.metadata.tables["report_runs"]
    assert "output_file_asset_id" in table.c
    assert "file_content" not in table.c
    assert "blob" not in table.c


def test_integration_connector_stores_credential_reference_not_secret_value() -> None:
    table = Base.metadata.tables["integration_connectors"]
    assert "credential_reference" in table.c
    assert "password" not in table.c
    assert "access_token" not in table.c


def test_operations_snapshot_is_projection_not_raw_log_blob() -> None:
    table = Base.metadata.tables["operational_health_snapshots"]
    assert "metrics" in table.c
    assert "summary" in table.c
    assert "raw_log" not in table.c
