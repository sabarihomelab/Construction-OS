from app.main import app
from app.modules.workforce.attendance_schemas import AttendanceDPRSummaryRead


def test_date_scoped_attendance_dpr_summary_route_is_available() -> None:
    path = "/api/v1/projects/{project_id}/workforce/attendance/dpr-summary"
    paths = app.openapi()["paths"]
    assert path in paths

    operation = paths[path]["get"]
    parameters = {item["name"] for item in operation["parameters"]}
    assert {"project_id", "attendance_date", "shift_code"} <= parameters


def test_attendance_dpr_summary_contract_is_field_safe() -> None:
    fields = set(AttendanceDPRSummaryRead.model_fields)
    assert fields == {
        "register_id",
        "project_id",
        "attendance_date",
        "shift_code",
        "rows",
    }
