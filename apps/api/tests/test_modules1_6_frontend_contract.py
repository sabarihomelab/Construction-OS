from app.main import create_app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState


def _paths() -> dict[str, dict[str, object]]:
    return create_app().openapi()["paths"]


def test_modules_1_to_6_have_stable_frontend_api_roots() -> None:
    paths = _paths()
    required = {
        # Module 1 — Company / Parties
        "/api/v1/organization",
        "/api/v1/organization/settings",
        "/api/v1/commercial/parties/{party_id}",
        "/api/v1/projects/{project_id}/commercial/party-assignments",
        # Module 2 — WBS / Cost Codes
        "/api/v1/projects/{project_id}/commercial/wbs",
        "/api/v1/projects/{project_id}/commercial/wbs/tree",
        "/api/v1/projects/{project_id}/commercial/wbs/{wbs_id}",
        # Module 3 — BOQ
        "/api/v1/projects/{project_id}/commercial/boqs",
        "/api/v1/projects/{project_id}/commercial/boqs/{boq_id}",
        "/api/v1/projects/{project_id}/commercial/boqs/{boq_id}/approve",
        "/api/v1/projects/{project_id}/commercial/boqs/{boq_id}/revisions",
        # Module 4 — Estimating / Budget
        "/api/v1/projects/{project_id}/estimating/estimates/{estimate_id}",
        "/api/v1/projects/{project_id}/estimating/estimates/{estimate_id}/submit",
        "/api/v1/projects/{project_id}/estimating/estimates/{estimate_id}/approve",
        "/api/v1/projects/{project_id}/estimating/budgets/{budget_id}/approve",
        # Module 5 — Workforce / Attendance
        "/api/v1/projects/{project_id}/workforce/attendance",
        "/api/v1/projects/{project_id}/workforce/attendance/{register_id}",
        "/api/v1/projects/{project_id}/workforce/attendance/{register_id}/submit",
        "/api/v1/projects/{project_id}/workforce/attendance/{register_id}/approve",
        "/api/v1/projects/{project_id}/workforce/attendance/{register_id}/history",
        # Module 6 — DPR / Reporting
        "/api/v1/projects/{project_id}/daily-reports",
        "/api/v1/projects/{project_id}/daily-reports/{report_id}",
        "/api/v1/projects/{project_id}/daily-reports/{report_id}/work-progress",
        "/api/v1/projects/{project_id}/daily-reports/{report_id}/report-generation",
        "/api/v1/projects/{project_id}/daily-reports/{report_id}/render-history",
        "/api/v1/projects/{project_id}/dpr-templates",
    }
    assert required.issubset(paths)


def test_modules_1_to_6_released_pages_are_visible_without_over_releasing_parent_modules() -> None:
    released = {
        "admin.company",
        "commercial.parties",
        "commercial.wbs",
        "commercial.boq",
        "estimating",
        "workforce",
        "field",
        "field.dpr_templates",
    }
    for key in released:
        assert FEATURES_BY_KEY[key].release_state == FeatureReleaseState.AVAILABLE

    assert FEATURES_BY_KEY["commercial"].release_state == FeatureReleaseState.PLANNED


def test_modules_1_to_6_frontend_permissions_exist_in_one_catalog() -> None:
    required = {
        "admin.settings.view",
        "admin.configuration.manage",
        "commercial.party.view",
        "commercial.party.manage",
        "commercial.wbs.view",
        "commercial.wbs.manage",
        "commercial.boq.view",
        "commercial.boq.manage",
        "commercial.boq.approve",
        "estimating.estimate.view",
        "estimating.estimate.manage",
        "estimating.estimate.submit",
        "estimating.estimate.approve",
        "estimating.budget.view",
        "estimating.budget.approve",
        "workforce.worker.view",
        "workforce.assignment.manage",
        "workforce.attendance.view",
        "workforce.attendance.create",
        "workforce.attendance.update",
        "workforce.attendance.submit",
        "workforce.attendance.approve",
        "field.daily_report.view",
        "field.daily_report.create",
        "field.daily_report.update",
        "field.daily_report.submit",
        "field.daily_report.approve",
        "field.dpr.template.view",
        "field.dpr.template.manage",
        "field.dpr.render",
    }
    assert required.issubset(PERMISSIONS_BY_KEY)
