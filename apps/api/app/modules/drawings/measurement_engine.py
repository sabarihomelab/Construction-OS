from decimal import Decimal, InvalidOperation, localcontext
from math import sqrt
from typing import Any

from app.modules.drawings.models import DrawingMeasurementType


class DrawingMeasurementError(ValueError):
    pass


Point = tuple[Decimal, Decimal]


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DrawingMeasurementError("Drawing coordinates must be numeric") from exc
    if not result.is_finite():
        raise DrawingMeasurementError("Drawing coordinates must be finite")
    return result


def _points(geometry: dict[str, object]) -> list[Point]:
    raw_points = geometry.get("points")
    if not isinstance(raw_points, list):
        raise DrawingMeasurementError("Measurement geometry requires a points array")
    points: list[Point] = []
    for raw in raw_points:
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise DrawingMeasurementError("Each drawing point must contain x and y")
        points.append((_decimal(raw[0]), _decimal(raw[1])))
    return points


def calibration_scale(
    *,
    point_a_x: Decimal,
    point_a_y: Decimal,
    point_b_x: Decimal,
    point_b_y: Decimal,
    real_length: Decimal,
) -> Decimal:
    if real_length <= 0:
        raise DrawingMeasurementError("Calibration real length must be greater than zero")
    dx = point_b_x - point_a_x
    dy = point_b_y - point_a_y
    with localcontext() as ctx:
        ctx.prec = 34
        drawing_length = Decimal(str(sqrt(float(dx * dx + dy * dy))))
        if drawing_length == 0:
            raise DrawingMeasurementError("Calibration points must be different")
        return real_length / drawing_length


def _polyline_length(points: list[Point]) -> Decimal:
    if len(points) < 2:
        raise DrawingMeasurementError("Length measurement requires at least two points")
    total = Decimal(0)
    for start, end in zip(points, points[1:], strict=False):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        total += Decimal(str(sqrt(float(dx * dx + dy * dy))))
    return total


def _polygon_area(points: list[Point]) -> Decimal:
    if len(points) < 3:
        raise DrawingMeasurementError("Area measurement requires at least three points")
    total = Decimal(0)
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        total += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(total) / Decimal(2)


def calculate_measurement(
    measurement_type: DrawingMeasurementType,
    geometry: dict[str, object],
    *,
    scale: Decimal | None,
) -> Decimal:
    points = _points(geometry)
    if measurement_type == DrawingMeasurementType.COUNT:
        count = geometry.get("count", len(points))
        if not isinstance(count, int) or count < 0:
            raise DrawingMeasurementError("Count must be a non-negative integer")
        return Decimal(count)

    if scale is None or scale <= 0:
        raise DrawingMeasurementError("A valid drawing calibration is required")

    if measurement_type == DrawingMeasurementType.LENGTH:
        return _polyline_length(points) * scale
    if measurement_type == DrawingMeasurementType.AREA:
        return _polygon_area(points) * scale * scale
    if measurement_type == DrawingMeasurementType.VOLUME:
        depth = _decimal(geometry.get("depth"))
        if depth < 0:
            raise DrawingMeasurementError("Volume depth cannot be negative")
        return _polygon_area(points) * scale * scale * depth
    raise DrawingMeasurementError("Unsupported drawing measurement type")
