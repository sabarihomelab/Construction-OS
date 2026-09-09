from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.metadata.models import CustomFieldType
from app.modules.metadata.schemas import CustomFieldDefinitionUpdate
from app.modules.metadata.service import MetadataValidationError, normalize_custom_value


def test_metadata_tables_are_registered() -> None:
    expected = {
        "custom_field_definitions",
        "custom_field_options",
        "custom_field_definition_revisions",
        "custom_field_values",
    }
    assert expected.issubset(Base.metadata.tables)


def test_definition_identity_and_type_are_not_mutable_update_fields() -> None:
    update_fields = CustomFieldDefinitionUpdate.model_fields
    assert "key" not in update_fields
    assert "entity_type" not in update_fields
    assert "field_type" not in update_fields


def test_custom_values_use_typed_columns_not_one_generic_value() -> None:
    table = Base.metadata.tables["custom_field_values"]
    assert "value" not in table.c
    assert {
        "text_value",
        "numeric_value",
        "boolean_value",
        "date_value",
        "datetime_value",
        "uuid_value",
        "json_value",
        "currency_code",
        "unit_code",
    }.issubset(set(table.c.keys()))
    assert table.c.numeric_value.type.precision == 30
    assert table.c.numeric_value.type.scale == 10


def test_currency_is_normalized_to_decimal_and_iso_code() -> None:
    normalized = normalize_custom_value(
        CustomFieldType.CURRENCY,
        {"amount": "1234.50", "currency": "usd"},
    )
    assert normalized.numeric_value == Decimal("1234.50")
    assert normalized.currency_code == "USD"


def test_measurement_preserves_numeric_value_and_unit_identity() -> None:
    normalized = normalize_custom_value(
        CustomFieldType.MEASUREMENT,
        {"value": "10.25", "unit": "ft"},
    )
    assert normalized.numeric_value == Decimal("10.25")
    assert normalized.unit_code == "ft"


def test_integer_rejects_fractional_value() -> None:
    with pytest.raises(MetadataValidationError):
        normalize_custom_value(CustomFieldType.INTEGER, "12.5")


def test_date_remains_date_only() -> None:
    normalized = normalize_custom_value(CustomFieldType.DATE, "2026-09-10")
    assert normalized.date_value == date(2026, 9, 10)
    with pytest.raises(MetadataValidationError):
        normalize_custom_value(CustomFieldType.DATE, datetime(2026, 9, 10, 12, 0, tzinfo=UTC))


def test_datetime_requires_timezone() -> None:
    with pytest.raises(MetadataValidationError):
        normalize_custom_value(CustomFieldType.DATETIME, "2026-09-10T12:00:00")

    normalized = normalize_custom_value(
        CustomFieldType.DATETIME,
        "2026-09-10T12:00:00+05:30",
    )
    assert normalized.datetime_value is not None
    assert normalized.datetime_value.utcoffset() is not None


def test_multi_select_rejects_duplicate_option_keys() -> None:
    with pytest.raises(MetadataValidationError):
        normalize_custom_value(CustomFieldType.MULTI_SELECT, ["north", "north"])


def test_email_is_canonicalized() -> None:
    normalized = normalize_custom_value(CustomFieldType.EMAIL, "ADMIN@Example.com")
    assert normalized.text_value == "admin@example.com"
