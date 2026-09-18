import inspect

from app.main import app
from app.modules.authorization.templates import ROLE_TEMPLATES_BY_KEY
from app.modules.files import service as file_service
from app.modules.financials import attachment_router
from app.modules.financials.attachment_schemas import FinancialAttachmentRead


def test_financial_attachment_routes_are_mounted() -> None:
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/projects/{project_id}/financials/site-expenses/{expense_id}/attachments"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/attachments"
        in paths
    )


def test_shared_file_link_service_pins_immutable_current_version() -> None:
    source = inspect.getsource(file_service.link_file_asset)

    assert "version_number = pinned_version or asset.current_version" in source
    assert "pinned_version=version_number" in source
    assert 'action="file.link.created"' in source
    assert "FileAsset.status == FileAssetStatus.ACTIVE" in source


def test_financial_attachment_routes_reuse_shared_file_links() -> None:
    source = inspect.getsource(attachment_router)

    assert "link_file_asset(" in source
    assert "list_entity_file_links(" in source
    assert "FileLink(" not in source


def test_site_expense_receipt_requires_domain_and_file_permissions() -> None:
    source = inspect.getsource(attachment_router.attach_site_expense_receipt)

    assert '"financials.site_expense.create"' in source
    assert '"files.file.upload"' in source
    assert 'relation_type="receipt"' in source


def test_vendor_bill_evidence_requires_domain_and_file_permissions() -> None:
    source = inspect.getsource(attachment_router.attach_vendor_bill_document)

    assert '"financials.payable.manage"' in source
    assert '"files.file.upload"' in source
    assert 'relation_type="vendor_invoice"' in source


def test_site_supervisor_can_capture_receipt_evidence_without_finance_module() -> None:
    role = ROLE_TEMPLATES_BY_KEY["site-supervisor"]

    assert {
        "files.file.view",
        "files.file.upload",
        "financials.site_expense.view",
        "financials.site_expense.create",
    } <= set(role.permission_keys)
    assert "financials.module.view" not in role.permission_keys


def test_accounts_finance_can_manage_financial_evidence_files() -> None:
    role = ROLE_TEMPLATES_BY_KEY["accounts-finance"]

    assert {
        "files.file.view",
        "files.file.download",
        "files.file.upload",
        "financials.site_expense.view",
        "financials.payable.view",
        "financials.payable.manage",
    } <= set(role.permission_keys)


def test_attachment_contract_exposes_pinned_evidence_version() -> None:
    fields = set(FinancialAttachmentRead.model_fields)

    assert {
        "link_id",
        "asset_id",
        "asset_name",
        "asset_current_version",
        "pinned_version",
        "relation_type",
        "created_at",
    } <= fields
