from inspect import getsource

from sqlalchemy import inspect

from app.modules.financials import commitment_router
from app.modules.financials.commitment_feeds import post_subcontract_commitment
from app.modules.financials.commitment_models import ProjectCommitmentAllocation
from app.modules.financials.commitment_schemas import ProjectCommitmentAllocationRead


def test_commitment_allocation_supports_exactly_one_source_line_type() -> None:
    mapper = inspect(ProjectCommitmentAllocation)
    columns = {column.key: column for column in mapper.columns}

    assert columns["source_line_id"].nullable is True
    assert columns["subcontract_line_id"].nullable is True

    constraint_names = {
        constraint.name for constraint in ProjectCommitmentAllocation.__table__.constraints
    }
    assert "fk_project_commitment_allocations_po_line_scope" in constraint_names
    assert "fk_project_commitment_allocations_subcontract_line_scope" in constraint_names
    assert "ck_project_commitment_allocations_source_line_choice" in constraint_names


def test_commitment_schema_exposes_both_lineage_sources() -> None:
    assert "source_line_id" in ProjectCommitmentAllocationRead.model_fields
    assert "subcontract_line_id" in ProjectCommitmentAllocationRead.model_fields


def test_subcontract_commitment_preserves_boq_and_wbs_lineage() -> None:
    source = getsource(post_subcontract_commitment)

    assert "CommitmentSourceType.SUBCONTRACT" in source
    assert "subcontract_line_id=line.id" in source
    assert "boq_item_id=line.boq_item_id" in source
    assert "wbs_code_id=line.wbs_code_id" in source
    assert "committed_total != subcontract.original_amount" in source
    assert '"tax_exclusive_subcontract_line_value"' in source


def test_financial_commitment_router_exposes_subcontract_posting() -> None:
    source = getsource(commitment_router)

    assert "from-subcontracts/{subcontract_id}" in source
    assert "post_subcontract_commitment" in source
