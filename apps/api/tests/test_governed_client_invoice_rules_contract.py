import inspect

from app.main import app
from app.modules.financials import governed_receivable_service, receivable_api
from app.modules.financials.governed_receivable_schemas import GovernedClientInvoiceFromRABillCreate
from app.modules.financials.rule_models import FinancialRuleSnapshot

CANONICAL_PATH = "/api/v1/projects/{project_id}/financials/receivables/invoices/from-ra-bill"


def test_canonical_ra_to_invoice_route_is_mounted_once() -> None:
    schema = app.openapi()
    assert CANONICAL_PATH in schema["paths"]
    matching = [
        route
        for route in receivable_api.router.routes
        if getattr(route, "path", "")
        == "/projects/{project_id}/financials/receivables/invoices/from-ra-bill"
    ]
    assert len(matching) == 1


def test_client_cannot_supply_authoritative_tax_or_withholding_values() -> None:
    fields = set(GovernedClientInvoiceFromRABillCreate.model_fields)
    assert fields == {"source_ra_bill_id", "invoice_date", "due_date", "notes"}
    assert fields.isdisjoint({"tax_rate", "tax_code", "withholding_amount"})


def test_invoice_rules_are_resolved_effective_at_invoice_date() -> None:
    source = inspect.getsource(
        governed_receivable_service.create_governed_client_invoice_from_ra_bill
    )
    assert "resolve_effective_configuration" in source
    assert 'module_key="financials"' in source
    assert "as_of=as_of" in source
    assert "GST_RULE_KEY" in source
    assert "WITHHOLDING_RULE_KEY" in source
    assert "FinancialRuleSnapshot" in source
    assert "configuration_version" in source
    assert "resolved_as_of" in source


def test_financial_rule_snapshot_preserves_rule_evidence() -> None:
    fields = set(FinancialRuleSnapshot.__table__.columns.keys())
    assert {
        "organization_id",
        "project_id",
        "entity_type",
        "entity_id",
        "rule_key",
        "source",
        "version",
        "effective_from",
        "applied_at",
        "snapshot_json",
    } <= fields


def test_governed_rule_service_has_no_hardcoded_common_statutory_rates() -> None:
    source = inspect.getsource(governed_receivable_service)
    assert 'GST_RULE_KEY = "financials.client_invoice.gst_rule"' in source
    assert 'WITHHOLDING_RULE_KEY = "financials.client_invoice.withholding_rule"' in source
    for literal in ('Decimal("18")', 'Decimal("18.00")', 'Decimal("10")', 'Decimal("10.00")'):
        assert literal not in source
