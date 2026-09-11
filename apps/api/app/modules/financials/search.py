from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.financials.job_cost_models import ProjectCostEntry, SiteExpense
from app.modules.financials.models import ProjectCommitment
from app.modules.financials.payables_models import VendorBill
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def site_expense_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(SiteExpense).where(
            SiteExpense.id == row_id,
            SiteExpense.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="site_expense",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="financials.site_expense.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.expense_number,
        subtitle=f"Site expense · {row.status.value}",
        body=row.description,
        keywords=[row.expense_number, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/financials/site-expenses/{row.id}",
        source_updated_at=row.updated_at,
    )


async def project_cost_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(ProjectCostEntry).where(
            ProjectCostEntry.id == row_id,
            ProjectCostEntry.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="project_cost_entry",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="financials.project_cost.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.entry_number,
        subtitle=f"Project cost · {row.source_type.value}",
        body=row.description,
        keywords=[row.entry_number, row.source_type.value, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/financials/job-cost/entries/{row.id}",
        source_updated_at=row.updated_at,
    )


async def project_commitment_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(ProjectCommitment).where(
            ProjectCommitment.id == row_id,
            ProjectCommitment.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="project_commitment",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="financials.project_cost.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.source_number,
        subtitle=f"Commitment · {row.source_type.value} · {row.status.value}",
        body=f"Committed {row.committed_amount} {row.currency_code}",
        keywords=[row.source_number, row.source_type.value, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/financials/commitments",
        source_updated_at=row.updated_at,
    )


async def vendor_bill_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(VendorBill).where(
            VendorBill.id == row_id,
            VendorBill.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="vendor_bill",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="financials.payable.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.bill_number,
        subtitle=f"Vendor bill · {row.status.value} · {row.match_status.value}",
        body=(
            f"Supplier invoice {row.supplier_invoice_number} · "
            f"{row.total_amount} {row.currency_code}"
        ),
        keywords=[
            row.bill_number,
            row.supplier_invoice_number,
            row.status.value,
            row.match_status.value,
            row.currency_code,
        ],
        route_hint=f"/projects/{row.project_id}/financials/vendor-bills/{row.id}",
        source_updated_at=row.updated_at,
    )


for entity_type, provider in (
    ("site_expense", site_expense_search_projection),
    ("project_cost_entry", project_cost_search_projection),
    ("project_commitment", project_commitment_search_projection),
    ("vendor_bill", vendor_bill_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
