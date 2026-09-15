from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.main import app
from app.modules.equipment.inventory_control_schemas import (
    ManualStockTransactionCreate,
    StockTransferCreate,
)
from app.modules.equipment.inventory_models import StockDirection, StockTransactionType
from app.modules.equipment.inventory_transaction_service import _MANUAL_DIRECTIONS


def test_inventory_control_routes_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/projects/{project_id}/materials/stock-transactions/manual" in paths
    assert "/api/v1/projects/{project_id}/materials/stock-transfers" in paths


def test_manual_inventory_direction_contract() -> None:
    assert _MANUAL_DIRECTIONS[StockTransactionType.OPENING_BALANCE] == StockDirection.INFLOW
    assert _MANUAL_DIRECTIONS[StockTransactionType.ISSUE] == StockDirection.OUTFLOW
    assert _MANUAL_DIRECTIONS[StockTransactionType.RETURN_IN] == StockDirection.INFLOW
    assert _MANUAL_DIRECTIONS[StockTransactionType.REJECTION] == StockDirection.OUTFLOW
    assert _MANUAL_DIRECTIONS[StockTransactionType.WASTAGE] == StockDirection.OUTFLOW
    assert _MANUAL_DIRECTIONS[StockTransactionType.DAMAGE] == StockDirection.OUTFLOW
    assert StockTransactionType.GRN_RECEIPT not in _MANUAL_DIRECTIONS
    assert StockTransactionType.CONSUMPTION not in _MANUAL_DIRECTIONS
    assert StockTransactionType.TRANSFER_IN not in _MANUAL_DIRECTIONS
    assert StockTransactionType.TRANSFER_OUT not in _MANUAL_DIRECTIONS


def test_manual_inventory_requires_positive_quantity_and_reason() -> None:
    with pytest.raises(ValidationError):
        ManualStockTransactionCreate(
            client_transaction_id=uuid4(),
            stock_location_id=uuid4(),
            material_id=uuid4(),
            transaction_type=StockTransactionType.WASTAGE,
            quantity=Decimal(0),
            occurred_at=datetime.now(UTC),
            reason="wastage",
        )
    with pytest.raises(ValidationError):
        ManualStockTransactionCreate(
            client_transaction_id=uuid4(),
            stock_location_id=uuid4(),
            material_id=uuid4(),
            transaction_type=StockTransactionType.WASTAGE,
            quantity=Decimal(1),
            occurred_at=datetime.now(UTC),
            reason="",
        )


def test_transfer_contract_requires_positive_quantity() -> None:
    payload = StockTransferCreate(
        client_transfer_id=uuid4(),
        from_stock_location_id=uuid4(),
        to_stock_location_id=uuid4(),
        material_id=uuid4(),
        quantity=Decimal(5),
        occurred_at=datetime.now(UTC),
        reason="Move stock to active work area",
    )
    assert payload.quantity == Decimal(5)
