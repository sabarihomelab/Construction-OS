import inspect

from app.main import app
from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.financials import (
    accounting_export_service,
    budget_control,
    commercial_control,
    receivable_service,
)
from app.modules.financials import service as financial_service
from app.modules.financials.job_cost_models import (
    ProjectCostEntry,
    ProjectCostSourceType,
    ProjectCostStatus,
    SiteCashDirection,
    SiteCashTransactionType,
    SiteExpenseStatus,
)
from app.modules.financials.models import ClientInvoiceStatus, ClientReceipt, ClientReceiptStatus
from app.modules.financials.schemas import ProjectCostRead


def test_financial_reversal_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/projects/{project_id}/financials/job-cost/entries/{entry_id}/reverse"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/financials/site-expenses/{expense_id}/reverse"
        in paths
    )


def test_project_cost_reversal_preserves_original_and_creates_linked_record() -> None:
    source = inspect.getsource(financial_service._reverse_project_cost_entry)

    assert "original.status = ProjectCostStatus.REVERSED" in source
    assert "source_type=ProjectCostSourceType.ADJUSTMENT" in source
    assert "reversal_of_entry_id=original.id" in source
    assert '"original_entry_date": original.entry_date.isoformat()' in source
    assert "reversal_reason=clean_reason" in source
    assert "reversed_by_membership_id = membership_id" in source
    assert "reversed_at = now" in source
    assert "db.delete(" not in source


def test_project_cost_reversal_mirrors_authoritative_allocation_lineage() -> None:
    source = inspect.getsource(financial_service._reverse_project_cost_entry)

    for field in (
        "cost_head_id=allocation.cost_head_id",
        "wbs_code_id=allocation.wbs_code_id",
        "boq_item_id=allocation.boq_item_id",
        "party_id=allocation.party_id",
        "worker_assignment_id=allocation.worker_assignment_id",
        "equipment_asset_id=allocation.equipment_asset_id",
        "material_id=allocation.material_id",
    ):
        assert field in source


def test_site_expense_reversal_restores_site_cash_and_cost() -> None:
    source = inspect.getsource(financial_service.reverse_posted_site_expense)

    assert "expense.status != SiteExpenseStatus.POSTED" in source
    assert "allow_site_expense=True" in source
    assert "transaction_type=SiteCashTransactionType.REVERSAL" in source
    assert "direction=SiteCashDirection.INFLOW" in source
    assert "amount=expense.gross_amount" in source
    assert "expense.status = SiteExpenseStatus.REVERSED" in source


def test_generic_cost_reversal_forces_site_expenses_through_cash_aware_flow() -> None:
    source = inspect.getsource(financial_service._reverse_project_cost_entry)

    assert "original.source_type == ProjectCostSourceType.SITE_EXPENSE" in source
    assert "Site expense cost must be reversed through the site expense reversal flow" in source


def test_current_cost_views_exclude_reversal_records() -> None:
    job_source = inspect.getsource(financial_service.job_cost_summary_rows)
    commercial_source = inspect.getsource(commercial_control.build_boq_commercial_control)
    budget_source = inspect.getsource(budget_control.build_budget_commercial_control)

    assert "ProjectCostEntry.reversal_of_entry_id.is_(None)" in job_source
    assert "ProjectCostEntry.reversal_of_entry_id.is_(None)" in commercial_source
    assert budget_source.count("ProjectCostEntry.reversal_of_entry_id.is_(None)") >= 2


def test_accounting_export_preserves_reversal_as_negative_history() -> None:
    source = inspect.getsource(accounting_export_service.build_cost_register_export)

    assert "ProjectCostStatus.REVERSED" in source
    assert "if entry.reversal_of_entry_id is not None" in source
    assert 'entry.configuration_context.get("original_entry_date")' in source
    assert "mapping.effective_from <= mapping_date" in source
    assert "-_money(allocation.amount)" in source


def test_project_cost_read_exposes_reversal_lineage() -> None:
    fields = set(ProjectCostRead.model_fields)

    assert {
        "reversed_by_membership_id",
        "reversed_at",
        "reversal_of_entry_id",
        "reversal_reason",
    } <= fields


def test_accounts_finance_has_controlled_reversal_permission() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert "financials.project_cost.adjust" in role.permission_keys


def test_reversal_model_contract_already_supports_history() -> None:
    assert ProjectCostSourceType.ADJUSTMENT.value == "adjustment"
    assert ProjectCostStatus.REVERSED.value == "reversed"
    assert SiteExpenseStatus.REVERSED.value == "reversed"
    assert SiteCashTransactionType.REVERSAL.value == "reversal"
    assert SiteCashDirection.INFLOW.value == "inflow"
    assert hasattr(ProjectCostEntry, "reversal_of_entry_id")



def test_client_receipt_reversal_route_is_mounted() -> None:
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/projects/{project_id}/financials/receivables/receipts/{receipt_id}/reverse"
        in paths
    )


def test_client_receipt_reversal_preserves_allocation_history() -> None:
    source = inspect.getsource(receivable_service.reverse_client_receipt)

    assert "original.status = ClientReceiptStatus.REVERSED" in source
    assert "status=ClientReceiptStatus.REVERSED" in source
    assert "reversal_of_receipt_id=original.id" in source
    assert "receipt_id=reversal.id" in source
    assert "invoice_id=allocation.invoice_id" in source
    assert "amount=allocation.amount" in source
    assert "db.delete(" not in source


def test_client_receipt_reversal_recalculates_invoice_payment_state() -> None:
    source = inspect.getsource(receivable_service.reverse_client_receipt)

    assert "received = await invoice_received_amount(" in source
    assert "invoice.status = ClientInvoiceStatus.ISSUED" in source
    assert "invoice.status = ClientInvoiceStatus.PAID" in source
    assert "invoice.status = ClientInvoiceStatus.PARTIALLY_PAID" in source


def test_received_cash_control_only_counts_posted_receipts() -> None:
    source = inspect.getsource(commercial_control.build_boq_commercial_control)

    assert "ClientReceipt.status == ClientReceiptStatus.POSTED" in source


def test_receipt_reversal_permission_is_assigned_to_finance() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert "financials.receipt.post" in role.permission_keys
    assert "financials.receipt.reverse" in role.permission_keys


def test_receipt_reversal_status_contract_is_explicit() -> None:
    assert ClientReceiptStatus.POSTED.value == "posted"
    assert ClientReceiptStatus.REVERSED.value == "reversed"
    assert ClientInvoiceStatus.ISSUED.value == "issued"



def test_receipt_reversal_is_project_scoped_and_database_unique() -> None:
    table = ClientReceipt.__table__
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("id", "project_id", "organization_id") in unique_sets
    assert (
        "reversal_of_receipt_id",
        "project_id",
        "organization_id",
    ) in unique_sets

    reversal_fk = next(
        constraint
        for constraint in table.foreign_key_constraints
        if constraint.name == "fk_client_receipts_reversal_scope"
    )
    assert tuple(
        element.target_fullname for element in reversal_fk.elements
    ) == (
        "client_receipts.id",
        "client_receipts.project_id",
        "client_receipts.organization_id",
    )


def test_reversal_services_lock_original_rows_before_mutation() -> None:
    cost_source = inspect.getsource(financial_service._reverse_project_cost_entry)
    receipt_source = inspect.getsource(receivable_service.reverse_client_receipt)

    assert ".with_for_update()" in cost_source
    assert ".with_for_update()" in receipt_source
