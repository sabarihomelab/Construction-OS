import inspect
from datetime import date
from decimal import Decimal
from uuid import uuid4
from xml.etree import ElementTree

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
    TallyPrimeVoucherLine,
)
from app.modules.financials.models import JournalSourceType


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



def test_generated_accounting_export_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/projects/{project_id}/financials/accounting-export/cost-register.xlsx"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/financials/accounting-export/tallyprime.xml"
        in paths
    )


def test_xlsx_serializer_produces_real_workbook_package() -> None:
    project_id = uuid4()
    export = AccountingCostRegisterExport(
        project_id=project_id,
        from_date=date(2026, 9, 1),
        to_date=date(2026, 9, 30),
        currency_code="INR",
        ready_for_export=True,
        row_count=0,
        mapped_row_count=0,
        missing_mapping_count=0,
        total_amount=Decimal("0.00"),
        rows=[],
    )

    payload = accounting_export_service.serialize_cost_register_xlsx(export)

    assert payload.startswith(b"PK")
    assert len(payload) > 100


def test_tally_xml_serializer_uses_official_voucher_import_shape() -> None:
    ledger_id = uuid4()
    voucher = TallyPrimeVoucher(
        journal_entry_id=uuid4(),
        voucher_number="JV-0001",
        voucher_date=date(2026, 9, 18),
        narration="Governed journal export",
        source_type=JournalSourceType.MANUAL,
        source_id=None,
        source_reference=None,
        debit_total=Decimal("100.00"),
        credit_total=Decimal("100.00"),
        lines=[
            TallyPrimeVoucherLine(
                line_number=1,
                ledger_account_id=ledger_id,
                ledger_code="EXP-001",
                ledger_name="Project Expense",
                wbs_code_id=None,
                party_id=None,
                description=None,
                debit_amount=Decimal("100.00"),
                credit_amount=Decimal("0.00"),
            ),
            TallyPrimeVoucherLine(
                line_number=2,
                ledger_account_id=uuid4(),
                ledger_code="CASH-001",
                ledger_name="Cash",
                wbs_code_id=None,
                party_id=None,
                description=None,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("100.00"),
            ),
        ],
    )
    preview = TallyPrimeExportPreview(
        project_id=uuid4(),
        from_date=None,
        to_date=None,
        ready_for_export=True,
        voucher_count=1,
        line_count=2,
        vouchers=[voucher],
    )

    payload = accounting_export_service.serialize_tallyprime_xml(preview)
    root = ElementTree.fromstring(payload)

    assert root.tag == "ENVELOPE"
    assert root.findtext("./HEADER/TALLYREQUEST") == "Import"
    assert root.findtext("./HEADER/TYPE") == "Data"
    assert root.findtext("./HEADER/ID") == "Vouchers"
    voucher_node = root.find("./BODY/DATA/TALLYMESSAGE/VOUCHER")
    assert voucher_node is not None
    assert voucher_node.findtext("DATE") == "20260918"
    assert voucher_node.findtext("VOUCHERTYPENAME") == "Journal"
    amounts = [
        node.findtext("AMOUNT")
        for node in voucher_node.findall("LEDGERENTRIES.LIST")
    ]
    assert amounts == ["-100.00", "100.00"]


def test_generated_exports_reuse_shared_file_storage_and_project_link() -> None:
    source = inspect.getsource(accounting_export_router._store_accounting_export)

    assert "store_generated_file(" in source
    assert "link_file_asset(" in source
    assert 'entity_type="project"' in source
    assert 'relation_type="accounting_export"' in source


def test_xlsx_export_still_blocks_unmapped_cost_heads() -> None:
    export = AccountingCostRegisterExport(
        project_id=uuid4(),
        from_date=None,
        to_date=None,
        currency_code="INR",
        ready_for_export=False,
        row_count=1,
        mapped_row_count=0,
        missing_mapping_count=1,
        total_amount=Decimal("10.00"),
        rows=[],
    )

    try:
        accounting_export_service.serialize_cost_register_xlsx(export)
    except Exception as exc:
        assert "complete ledger mapping before export" in str(exc)
    else:
        raise AssertionError("Unmapped Cost Heads must block workbook generation")
