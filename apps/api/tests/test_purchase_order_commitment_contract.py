from fastapi.routing import iter_route_contexts
from sqlalchemy import Numeric

from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.financials.api import router as financial_router
from app.modules.financials.commitment_models import ProjectCommitmentAllocation
from app.modules.financials.models import CommitmentSourceType, ProjectCommitment
from app.modules.search.providers import search_projection_providers


def _fk_targets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in Base.metadata.tables[table_name].foreign_key_constraints
    }


def test_commitment_allocation_table_is_registered_and_project_scoped() -> None:
    assert ProjectCommitmentAllocation.__tablename__ in Base.metadata.tables
    targets = _fk_targets(ProjectCommitmentAllocation.__tablename__)
    assert (
        "project_commitments.id",
        "project_commitments.project_id",
        "project_commitments.organization_id",
    ) in targets
    assert (
        "purchase_order_lines.id",
        "purchase_order_lines.project_id",
        "purchase_order_lines.organization_id",
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
    assert ("materials.id", "materials.organization_id") in targets


def test_purchase_order_commitment_preserves_net_tax_and_gross_snapshots() -> None:
    table = Base.metadata.tables[ProjectCommitmentAllocation.__tablename__]
    for column_name in ("committed_amount", "tax_amount", "gross_amount"):
        column_type = table.c[column_name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 20
        assert column_type.scale == 2

    quantity_type = table.c.quantity.type
    assert isinstance(quantity_type, Numeric)
    assert quantity_type.precision == 20
    assert quantity_type.scale == 4


def test_project_commitment_remains_one_source_record_per_purchase_order() -> None:
    assert CommitmentSourceType.PURCHASE_ORDER.value == "purchase_order"
    table = Base.metadata.tables[ProjectCommitment.__tablename__]
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("project_id", "source_type", "source_id") in unique_column_sets


def test_purchase_order_commitment_routes_are_composed() -> None:
    paths = {context.path for context in iter_route_contexts(financial_router.routes)}
    assert "/projects/{project_id}/financials/commitments" in paths
    assert (
        "/projects/{project_id}/financials/commitments/from-purchase-orders/{purchase_order_id}"
        in paths
    )


def test_project_commitments_are_searchable() -> None:
    assert search_projection_providers.contains("project_commitment")
