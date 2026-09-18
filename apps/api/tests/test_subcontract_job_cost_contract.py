import inspect

from app.main import app
from app.modules.financials import subcontract_cost_feeds
from app.modules.financials.job_cost_models import ProjectCostSourceType


def test_subcontract_claim_job_cost_route_is_mounted() -> None:
    path = (
        "/api/v1/projects/{project_id}/financials/job-cost/"
        "from-subcontract-claims/{claim_id}"
    )
    assert path in app.openapi()["paths"]


def test_subcontract_claim_is_a_supported_project_cost_source() -> None:
    assert ProjectCostSourceType.SUBCONTRACT_CLAIM.value == "subcontract_claim"


def test_subcontract_claim_cost_uses_gross_certified_work_and_boq_lineage() -> None:
    source = inspect.getsource(subcontract_cost_feeds.post_subcontract_claim_cost)

    assert "gross_certified_work" in source
    assert "line.certified_amount" in source
    assert "gross_certified_work != claim.gross_amount" in source
    assert "cost_basis\": \"gross_certified_subcontract_work" in source
    assert "boq_item_id=contract_line.boq_item_id" in source
    assert "wbs_code_id=contract_line.wbs_code_id" in source
    assert "party_id=subcontract.contractor_party_id" in source


def test_subcontract_claim_cost_does_not_use_net_payable_as_project_cost() -> None:
    source = inspect.getsource(subcontract_cost_feeds.post_subcontract_claim_cost)

    assert "total_amount=gross_certified_work" in source
    assert "amount=claim_line.certified_amount" in source
    assert "net_certified_payable" in source
    assert "total_amount=claim.certified_amount" not in source
