from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Numeric

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.financials.job_cost_models import (
    CostHead,
    ProjectCostAllocation,
    ProjectCostEntry,
    SiteCashAccount,
    SiteCashTransaction,
    SiteExpense,
)
from app.modules.financials.router import router
from app.modules.financials.schemas import SiteExpenseCreate
from app.modules.financials.search import project_cost_search_projection, site_expense_search_projection
from app.modules.search.bootstrap import register_builtin_search_providers
from app.modules.search.providers import search_projection_providers
from app.runtime.modules import MODULES_BY_KEY, resolve_runtime_modules


def _constraint_names(table_name: str) -> set[str | None]:
    return {constraint.name for constraint in Base.metadata.tables[table_name].constraints}


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables[table_name].foreign_key_constraints
    }


def test_financial_and_job_cost_tables_are_registered() -> None:
    expected = {
        "ledger_accounts",
        "journal_entries",
        "journal_lines",
        "project_commitments",
        "client_invoices",
        CostHead.__tablename__,
        ProjectCostEntry.__tablename__,
        ProjectCostAllocation.__tablename__,
        SiteCashAccount.__tablename__,
        SiteExpense.__tablename__,
        SiteCashTransaction.__tablename__,
    }
    assert expected.issubset(Base.metadata.tables)


def test_project_cost_allocations_are_tenant_and_project_safe() -> None:
    targets = _fk_targets("project_cost_allocations")
    assert (
        "project_cost_entries.id",
        "project_cost_entries.project_id",
        "project_cost_entries.organization_id",
    ) in targets
    assert (
        "project_worker_assignments.id",
        "project_worker_assignments.project_id",
        "project_worker_assignments.organization_id",
    ) in targets
    assert (
        "project_wbs_codes.id",
        "project_wbs_codes.project_id",
        "project_wbs_codes.organization_id",
    ) in targets
    assert (
        "project_boq_items.id",
        "project_boq_items.project_id",
        "project_boq_items.organization_id",
    ) in targets


def test_financial_amounts_use_fixed_precision_and_posting_constraints() -> None:
    assert isinstance(Base.metadata.tables["project_cost_entries"].c.total_amount.type, Numeric)
    assert isinstance(Base.metadata.tables["project_cost_allocations"].c.amount.type, Numeric)
    assert isinstance(Base.metadata.tables["site_expenses"].c.gross_amount.type, Numeric)
    assert "ck_project_cost_entries_amount" in _constraint_names("project_cost_entries")
    assert "ck_site_expenses_gross_amount" in _constraint_names("site_expenses")
    assert "ck_journal_lines_one_sided" in _constraint_names("journal_lines")


def test_site_expense_schema_requires_exact_cost_allocation() -> None:
    with pytest.raises(ValidationError):
        SiteExpenseCreate(
            expense_date="2026-09-11",
            description="Site transport",
            gross_amount=Decimal(100),
            allocations=[
                {
                    "cost_head_id": uuid4(),
                    "amount": Decimal(90),
                }
            ],
        )


def test_financial_permissions_separate_setup_site_cash_and_posting() -> None:
    required = {
        "financials.module.view",
        "financials.cost_head.view",
        "financials.cost_head.manage",
        "financials.ledger.view",
        "financials.ledger.manage",
        "financials.project_cost.view",
        "financials.project_cost.post",
        "financials.site_cash.view",
        "financials.site_cash.manage",
        "financials.site_expense.view",
        "financials.site_expense.create",
        "financials.site_expense.approve",
        "financials.site_expense.post",
    }
    assert required.issubset(PERMISSIONS_BY_KEY)


def test_financials_are_runtime_selectable_with_commercial_dependency() -> None:
    manifest = MODULES_BY_KEY["financials"]
    assert manifest.dependencies == ("commercial",)
    assert {"workforce", "equipment", "procurement", "subcontracts"}.issubset(
        manifest.integrates_with
    )
    resolved = {item.key for item in resolve_runtime_modules("financials")}
    assert {"projects", "commercial", "financials"}.issubset(resolved)
    assert "workforce" not in resolved


def test_financial_feature_uses_new_permission_and_stays_planned() -> None:
    feature = FEATURES_BY_KEY["financials"]
    assert feature.required_permissions == ("financials.module.view",)
    assert feature.release_state == FeatureReleaseState.PLANNED


def test_financial_router_exposes_project_scoped_site_expense_and_job_cost_contracts() -> None:
    paths = {route.path for route in router.routes if hasattr(route, "path")}
    assert "/financials/cost-heads" in paths
    assert "/financials/ledger-accounts" in paths
    assert "/projects/{project_id}/financials/site-cash" in paths
    assert "/projects/{project_id}/financials/site-expenses" in paths
    assert "/projects/{project_id}/financials/site-expenses/{expense_id}/approve" in paths
    assert "/projects/{project_id}/financials/site-expenses/{expense_id}/post" in paths
    assert "/projects/{project_id}/financials/job-cost/summary" in paths


def test_financial_search_projections_use_shared_registry() -> None:
    register_builtin_search_providers()
    assert search_projection_providers.get("site_expense") is site_expense_search_projection
    assert (
        search_projection_providers.get("project_cost_entry")
        is project_cost_search_projection
    )
