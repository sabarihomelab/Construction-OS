import inspect

from app.main import app
from app.modules.authorization.catalog import PERMISSIONS_BY_KEY
from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.financials import accounting_export_router, accounting_export_service
from app.modules.financials.accounting_export_schemas import (
    AccountingCostRegisterExport,
    AccountingCostRegisterRow,
    AccountingExportAdapter,
    TallyPrimeExportPreview,
    TallyPrimeVoucher,
)


def test_accounting_export_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/projects/{project_id}/financials/accounting-export/cost-register"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/financials/accounting-export/cost-register.csv"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/financials/accounting-export/tallyprime-preview"
        in paths
    )


def test_accounting_export_permissions_are_explicit() -> None:
    assert "financials.accounting_export.view" in PERMISSIONS_BY_KEY
    assert "financials.accounting_export.export" in PERMISSIONS_BY_KEY


def test_accounts_finance_can_preview_and_export_accounting_data() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert {
        "financials.accounting_export.view",
        "financials.accounting_export.export",
    } <= set(role.permission_keys)


def test_company_management_has_read_only_accounting_export_visibility() -> None:
    role = ROLE_TEMPLATES_BY_KEY["company-management"]

    assert "financials.accounting_export.view" in role.permission_keys
    assert "financials.accounting_export.export" not in role.permission_keys


def test_cost_register_contract_preserves_authoritative_lineage() -> None:
    fields = set(AccountingCostRegisterRow.model_fields)

    assert {
        "project_cost_entry_id",
        "source_type",
        "source_id",
        "source_reference",
        "cost_head_id",
        "ledger_account_id",
        "mapping_status",
        "mapping_effective_from",
        "wbs_code_id",
        "boq_item_id",
        "party_id",
        "amount",
        "currency_code",
    } <= fields
    assert AccountingCostRegisterExport.model_fields["adapter"].default == (
        AccountingExportAdapter.COST_REGISTER_CSV
    )


def test_cost_register_uses_only_posted_cost_and_effective_ledger_mapping() -> None:
    source = inspect.getsource(accounting_export_service.build_cost_register_export)

    assert "ProjectCostStatus.POSTED" in source
    assert "ProjectCostStatus.REVERSED" in source
    assert "mapping.effective_from <= entry.entry_date" in source
    assert "mapping.effective_to is None or mapping.effective_to >= entry.entry_date" in source
    assert "ready_for_export=missing_mapping_count == 0" in source


def test_csv_download_blocks_missing_cost_head_mapping() -> None:
    source = inspect.getsource(accounting_export_router.download_cost_register_csv)

    assert "if not export.ready_for_export:" in source
    assert "complete ledger mapping before export" in source
    assert '"financials.accounting_export.export"' in source


def test_tally_adapter_exports_only_posted_balanced_journals() -> None:
    source = inspect.getsource(accounting_export_service.build_tallyprime_preview)

    assert "JournalEntry.status == JournalStatus.POSTED" in source
    assert "debit_total != credit_total" in source
    assert "is not balanced for TallyPrime export" in source
    assert TallyPrimeExportPreview.model_fields["adapter"].default == (
        AccountingExportAdapter.TALLY_PRIME_V1
    )


def test_tally_voucher_contract_keeps_source_and_ledger_traceability() -> None:
    fields = set(TallyPrimeVoucher.model_fields)

    assert {
        "journal_entry_id",
        "voucher_number",
        "voucher_date",
        "source_type",
        "source_id",
        "source_reference",
        "debit_total",
        "credit_total",
        "lines",
    } <= fields


def test_accounting_export_is_projection_only() -> None:
    source = inspect.getsource(accounting_export_service)

    assert "db.add(" not in source
    assert "db.delete(" not in source
    assert "await db.flush()" not in source
