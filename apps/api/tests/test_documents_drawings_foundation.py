from decimal import Decimal

import pytest
from sqlalchemy.dialects.postgresql import JSONB

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.drawings.measurement_engine import (
    DrawingMeasurementError,
    calculate_measurement,
    calibration_scale,
)
from app.modules.drawings.models import DrawingMeasurementType, DrawingRevisionStatus
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState


def test_document_and_drawing_tables_are_registered() -> None:
    expected = {
        "document_folders",
        "documents",
        "document_revisions",
        "specification_sections",
        "drawing_sets",
        "drawing_sheets",
        "drawing_revisions",
        "drawing_render_packages",
        "drawing_calibrations",
        "drawing_markups",
        "drawing_measurements",
        "drawing_pins",
        "drawing_comparisons",
    }
    assert expected.issubset(Base.metadata.tables)


def test_document_and_drawing_permissions_are_registered() -> None:
    expected = {
        "documents.document.view",
        "documents.document.create",
        "documents.document.publish",
        "documents.document.manage",
        "drawings.drawing.view",
        "drawings.drawing.revise",
        "drawings.drawing.publish",
        "drawings.markup.manage",
        "drawings.measurement.manage",
        "drawings.comparison.run",
        "drawings.drawing.manage",
    }
    assert expected.issubset(PERMISSIONS_BY_KEY)


def test_document_and_drawing_features_stay_hidden_until_ui_is_ready() -> None:
    assert FEATURES_BY_KEY["documents"].release_state == FeatureReleaseState.PLANNED
    assert FEATURES_BY_KEY["drawings"].release_state == FeatureReleaseState.PLANNED
    assert FEATURES_BY_KEY["drawings"].offline_enabled


def test_drawing_metadata_uses_jsonb_in_runtime_model() -> None:
    for table_name, column_name in (
        ("drawing_revisions", "geometry_metadata"),
        ("drawing_render_packages", "manifest"),
        ("drawing_markups", "geometry"),
        ("drawing_measurements", "geometry"),
        ("drawing_comparisons", "result_manifest"),
    ):
        assert isinstance(Base.metadata.tables[table_name].c[column_name].type, JSONB)


def test_drawing_revision_has_render_ready_state() -> None:
    assert DrawingRevisionStatus.READY.value == "ready"


def test_calibration_and_length_measurement_are_decimal_and_reproducible() -> None:
    scale = calibration_scale(
        point_a_x=Decimal(0),
        point_a_y=Decimal(0),
        point_b_x=Decimal(10),
        point_b_y=Decimal(0),
        real_length=Decimal(20),
    )
    value = calculate_measurement(
        DrawingMeasurementType.LENGTH,
        {"points": [[0, 0], [3, 4]]},
        scale=scale,
    )
    assert scale == Decimal(2)
    assert value == Decimal(10)


def test_area_measurement_uses_calibration_squared() -> None:
    value = calculate_measurement(
        DrawingMeasurementType.AREA,
        {"points": [[0, 0], [4, 0], [4, 3], [0, 3]]},
        scale=Decimal(2),
    )
    assert value == Decimal(48)


def test_volume_measurement_uses_area_and_depth() -> None:
    value = calculate_measurement(
        DrawingMeasurementType.VOLUME,
        {"points": [[0, 0], [2, 0], [2, 2], [0, 2]], "depth": "3"},
        scale=Decimal(2),
    )
    assert value == Decimal(48)


def test_uncalibrated_length_is_rejected() -> None:
    with pytest.raises(DrawingMeasurementError):
        calculate_measurement(
            DrawingMeasurementType.LENGTH,
            {"points": [[0, 0], [1, 1]]},
            scale=None,
        )


def test_count_does_not_require_calibration() -> None:
    value = calculate_measurement(
        DrawingMeasurementType.COUNT,
        {"points": [[0, 0], [1, 1]], "count": 7},
        scale=None,
    )
    assert value == Decimal(7)
