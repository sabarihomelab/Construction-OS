from datetime import date
from uuid import uuid4

import pytest
from fastapi.routing import iter_route_contexts
from pydantic import ValidationError

from app.modules.financials.api import router
from app.modules.financials.mapping_schemas import CostHeadLedgerMappingEnd
from app.modules.financials.schemas import CostHeadLedgerMappingCreate


def test_cost_head_ledger_mapping_routes_are_composed() -> None:
    paths = {context.path for context in iter_route_contexts(router.routes)}
    assert "/financials/cost-heads/{cost_head_id}/ledger-mappings" in paths
    assert (
        "/financials/cost-heads/{cost_head_id}/ledger-mappings/{mapping_id}/end" in paths
    )


def test_cost_head_mapping_create_rejects_invalid_date_range() -> None:
    with pytest.raises(ValidationError):
        CostHeadLedgerMappingCreate(
            ledger_account_id=uuid4(),
            effective_from=date(2026, 9, 11),
            effective_to=date(2026, 9, 10),
        )


def test_cost_head_mapping_end_is_revision_protected() -> None:
    payload = CostHeadLedgerMappingEnd(
        expected_revision=2,
        effective_to=date(2026, 12, 31),
        reason="New ledger mapping starts next period",
    )
    assert payload.expected_revision == 2
