from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.financials.api import router
from app.modules.financials.cost_feeds import _entry_cost
from app.modules.financials.feed_schemas import LabourTimeCostPost
from app.modules.financials.service import FinancialValidationError
from app.modules.workforce.models import ProjectWorkerRate, TimeEntry, WageBasis
from app.runtime.modules import MODULES_BY_KEY


def test_financial_runtime_uses_composed_router() -> None:
    assert MODULES_BY_KEY["financials"].api_router == "app.modules.financials.api:router"
    paths = {route.path for route in router.routes if hasattr(route, "path")}
    assert "/projects/{project_id}/financials/job-cost/from-timecards/{timecard_id}" in paths


def test_labour_cost_request_cannot_inject_tenant_project_worker_or_rate() -> None:
    assert set(LabourTimeCostPost.model_fields) == {"labour_cost_head_id"}


def test_hourly_entry_cost_uses_effective_rate_components() -> None:
    entry = TimeEntry(
        organization_id=uuid4(),
        timecard_id=uuid4(),
        work_date=date(2026, 9, 11),
        regular_hours=Decimal(8),
        overtime_hours=Decimal(2),
        double_time_hours=Decimal(0),
    )
    rate = ProjectWorkerRate(
        organization_id=uuid4(),
        project_id=uuid4(),
        assignment_id=uuid4(),
        worker_id=uuid4(),
        wage_basis=WageBasis.HOURLY,
        regular_rate=Decimal(100),
        overtime_rate=Decimal(150),
        currency_code="INR",
        effective_from=date(2026, 9, 1),
    )
    assert _entry_cost(entry, rate) == Decimal("1100.00")


def test_hourly_entry_cost_never_guesses_missing_overtime_rate() -> None:
    entry = TimeEntry(
        organization_id=uuid4(),
        timecard_id=uuid4(),
        work_date=date(2026, 9, 11),
        regular_hours=Decimal(8),
        overtime_hours=Decimal(1),
        double_time_hours=Decimal(0),
    )
    rate = ProjectWorkerRate(
        organization_id=uuid4(),
        project_id=uuid4(),
        assignment_id=uuid4(),
        worker_id=uuid4(),
        wage_basis=WageBasis.HOURLY,
        regular_rate=Decimal(100),
        overtime_rate=None,
        currency_code="INR",
        effective_from=date(2026, 9, 1),
    )
    with pytest.raises(FinancialValidationError):
        _entry_cost(entry, rate)
