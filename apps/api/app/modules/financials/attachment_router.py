from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.files.service import (
    FileValidationError,
    link_file_asset,
    list_entity_file_links,
)
from app.modules.financials.attachment_schemas import (
    FinancialAttachmentCreate,
    FinancialAttachmentRead,
)
from app.modules.financials.job_cost_models import SiteExpense
from app.modules.financials.payables_models import VendorBill
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["financials"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={
            key: set(values) for key, values in context.project_permissions.items()
        },
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


async def _require_site_expense(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    expense_id: UUID,
) -> SiteExpense:
    row = await db.scalar(
        select(SiteExpense).where(
            SiteExpense.id == expense_id,
            SiteExpense.organization_id == organization_id,
            SiteExpense.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site expense not found")
    return row


async def _require_vendor_bill(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    vendor_bill_id: UUID,
) -> VendorBill:
    row = await db.scalar(
        select(VendorBill).where(
            VendorBill.id == vendor_bill_id,
            VendorBill.organization_id == organization_id,
            VendorBill.project_id == project_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor bill not found")
    return row


def _attachment_reads(rows) -> list[FinancialAttachmentRead]:
    return [
        FinancialAttachmentRead(
            link_id=link.id,
            asset_id=asset.id,
            asset_name=asset.name,
            asset_current_version=asset.current_version,
            pinned_version=link.pinned_version or asset.current_version,
            relation_type=link.relation_type,
            created_at=link.created_at,
        )
        for link, asset in rows
    ]


@router.get(
    "/projects/{project_id}/financials/site-expenses/{expense_id}/attachments",
    response_model=list[FinancialAttachmentRead],
)
async def list_site_expense_attachments(
    project_id: UUID,
    expense_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[FinancialAttachmentRead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.view")
    _require_project_permission(context, project_id, "files.file.view")
    await _require_site_expense(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        expense_id=expense_id,
    )
    return _attachment_reads(
        await list_entity_file_links(
            db,
            organization_id=context.organization_id,
            entity_type="site_expense",
            entity_id=expense_id,
        )
    )


@router.post(
    "/projects/{project_id}/financials/site-expenses/{expense_id}/attachments",
    response_model=FinancialAttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def attach_site_expense_receipt(
    project_id: UUID,
    expense_id: UUID,
    payload: FinancialAttachmentCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> FinancialAttachmentRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.site_expense.create")
    _require_project_permission(context, project_id, "files.file.upload")
    await _require_site_expense(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        expense_id=expense_id,
    )
    try:
        link = await link_file_asset(
            db,
            organization_id=context.organization_id,
            entity_type="site_expense",
            entity_id=expense_id,
            asset_id=payload.asset_id,
            relation_type="receipt",
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        rows = await list_entity_file_links(
            db,
            organization_id=context.organization_id,
            entity_type="site_expense",
            entity_id=expense_id,
        )
        return next(item for item in _attachment_reads(rows) if item.link_id == link.id)
    except FileValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/attachments",
    response_model=list[FinancialAttachmentRead],
)
async def list_vendor_bill_attachments(
    project_id: UUID,
    vendor_bill_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[FinancialAttachmentRead]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.view")
    _require_project_permission(context, project_id, "files.file.view")
    await _require_vendor_bill(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        vendor_bill_id=vendor_bill_id,
    )
    return _attachment_reads(
        await list_entity_file_links(
            db,
            organization_id=context.organization_id,
            entity_type="vendor_bill",
            entity_id=vendor_bill_id,
        )
    )


@router.post(
    "/projects/{project_id}/financials/vendor-bills/{vendor_bill_id}/attachments",
    response_model=FinancialAttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def attach_vendor_bill_document(
    project_id: UUID,
    vendor_bill_id: UUID,
    payload: FinancialAttachmentCreate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> FinancialAttachmentRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "financials.payable.manage")
    _require_project_permission(context, project_id, "files.file.upload")
    await _require_vendor_bill(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        vendor_bill_id=vendor_bill_id,
    )
    try:
        link = await link_file_asset(
            db,
            organization_id=context.organization_id,
            entity_type="vendor_bill",
            entity_id=vendor_bill_id,
            asset_id=payload.asset_id,
            relation_type="vendor_invoice",
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        rows = await list_entity_file_links(
            db,
            organization_id=context.organization_id,
            entity_type="vendor_bill",
            entity_id=vendor_bill_id,
        )
        return next(item for item in _attachment_reads(rows) if item.link_id == link.id)
    except FileValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
