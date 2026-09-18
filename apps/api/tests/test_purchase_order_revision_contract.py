import inspect
from pathlib import Path

from app.main import app
from app.modules.procurement import po_revision_service
from app.modules.procurement.po_revision_models import PurchaseOrderRevision


def test_purchase_order_revision_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]
    assert (
        "/api/v1/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/revisions"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/procurement/purchase-orders/{purchase_order_id}/amendments"
        in paths
    )


def test_purchase_order_revision_model_is_versioned_and_snapshot_based() -> None:
    fields = set(PurchaseOrderRevision.__table__.columns.keys())
    assert {
        "purchase_order_id",
        "version_number",
        "issued_at",
        "snapshot_json",
        "superseded_reason",
    } <= fields


def test_purchase_order_amendment_preserves_downstream_history_boundaries() -> None:
    source = inspect.getsource(po_revision_service.start_purchase_order_amendment)

    assert "po.status != PurchaseOrderStatus.ISSUED" in source
    assert "GoodsReceipt.purchase_order_id == purchase_order_id" in source
    assert "ProjectCommitment.source_id == purchase_order_id" in source
    assert "latest_revision.superseded_reason" in source
    assert "delete(PurchaseOrderLine)" in source
    assert "add_purchase_order_line" in source


def test_purchase_order_issue_snapshot_is_database_enforced() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260916_0061_purchase_order_revision_history.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE TRIGGER trg_purchase_order_issue_revision" in migration
    assert "NEW.status = 'issued'" in migration
    assert "purchase_order_revisions" in migration
    assert "jsonb_agg" in migration
    assert "boq_item_id" in migration
    assert "wbs_code_id" in migration
