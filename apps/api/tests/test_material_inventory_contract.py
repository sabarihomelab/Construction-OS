from fastapi.routing import iter_route_contexts
from sqlalchemy import Numeric

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.equipment.api import router as equipment_router
from app.modules.equipment.consumption_schemas import MaterialConsumptionCreate
from app.modules.equipment.inventory_models import (
    MaterialStockLocation,
    MaterialStockTransaction,
    StockDirection,
    StockSourceType,
    StockTransactionType,
)
from app.modules.procurement.models import GoodsReceipt
from app.modules.procurement.schemas import GoodsReceiptCreate, GoodsReceiptReceiveAction


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables[table_name].foreign_key_constraints
    }


def test_stock_location_and_ledger_tables_are_registered() -> None:
    assert MaterialStockLocation.__tablename__ in Base.metadata.tables
    assert MaterialStockTransaction.__tablename__ in Base.metadata.tables


def test_stock_ledger_has_no_mutable_balance_column() -> None:
    columns = set(Base.metadata.tables[MaterialStockTransaction.__tablename__].c.keys())
    assert "balance" not in columns
    assert "quantity_on_hand" not in columns
    quantity_type = Base.metadata.tables[MaterialStockTransaction.__tablename__].c.quantity.type
    assert isinstance(quantity_type, Numeric)
    assert quantity_type.precision == 20
    assert quantity_type.scale == 4


def test_inventory_references_are_project_scoped() -> None:
    location_scope = (
        "material_stock_locations.id",
        "material_stock_locations.project_id",
        "material_stock_locations.organization_id",
    )
    assert location_scope in _fk_targets("material_stock_transactions")
    assert location_scope in _fk_targets("goods_receipts")
    assert location_scope in _fk_targets("material_consumptions")


def test_goods_receipt_can_carry_or_supply_stock_location_at_receive_time() -> None:
    assert "stock_location_id" in GoodsReceiptCreate.model_fields
    assert GoodsReceiptCreate.model_fields["stock_location_id"].is_required() is False
    assert "stock_location_id" in GoodsReceiptReceiveAction.model_fields
    assert "stock_location_id" in Base.metadata.tables[GoodsReceipt.__tablename__].c


def test_material_consumption_requires_exact_stock_location() -> None:
    field = MaterialConsumptionCreate.model_fields["stock_location_id"]
    assert field.is_required()


def test_inventory_source_types_separate_receipt_and_consumption() -> None:
    assert StockSourceType.GOODS_RECEIPT.value == "goods_receipt"
    assert StockSourceType.MATERIAL_CONSUMPTION.value == "material_consumption"
    assert StockTransactionType.GRN_RECEIPT.value == "grn_receipt"
    assert StockTransactionType.CONSUMPTION.value == "consumption"
    assert StockDirection.INFLOW.value == "inflow"
    assert StockDirection.OUTFLOW.value == "outflow"


def test_inventory_routes_are_composed_without_manual_adjustment_endpoint() -> None:
    paths = {context.path for context in iter_route_contexts(equipment_router.routes)}
    assert "/projects/{project_id}/materials/stock-locations" in paths
    assert "/projects/{project_id}/materials/stock-transactions" in paths
    assert "/projects/{project_id}/materials/stock-balances" in paths
    assert not any("adjust" in path for path in paths if "/materials/stock-" in path)
