from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import BOQ, MeasurementEntry, Party, RABill, WBSCode
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def party_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(Party).where(Party.id == row_id, Party.organization_id == organization_id)
    )
    if row is None:
        return None
    body = "\n".join(
        value
        for value in (
            row.legal_name,
            row.email,
            row.phone,
            row.locality,
            row.state_name,
            row.gstin,
        )
        if value
    )
    return SearchProjection(
        entity_type="commercial_party",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="commercial.party.view",
        title=row.name,
        subtitle=f"{row.code} · {row.party_type.value}",
        body=body,
        keywords=[row.code, row.party_type.value, row.status.value],
        route_hint=f"/commercial/parties/{row.id}",
        source_updated_at=row.updated_at,
    )


async def wbs_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(WBSCode).where(
            WBSCode.id == row_id,
            WBSCode.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="wbs_code",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="commercial.wbs.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=f"{row.code} · {row.name}",
        subtitle=row.kind.value,
        body=row.description or "",
        keywords=[row.code, row.name, row.kind.value, row.status.value],
        route_hint=f"/projects/{row.project_id}/commercial/wbs",
        source_updated_at=row.updated_at,
    )


async def boq_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(BOQ).where(BOQ.id == row_id, BOQ.organization_id == organization_id)
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="boq",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="commercial.boq.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=row.name,
        subtitle=f"{row.code} · {row.status.value}",
        body=row.description or "",
        keywords=[row.code, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/commercial/boqs/{row.id}",
        source_updated_at=row.updated_at,
    )


async def measurement_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(MeasurementEntry).where(
            MeasurementEntry.id == row_id,
            MeasurementEntry.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="measurement_entry",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="commercial.measurement.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=f"Measurement #{row.entry_number}",
        subtitle=f"{row.quantity} {row.unit_code} · {row.status.value}",
        body="\n".join(value for value in (row.location, row.description) if value),
        keywords=[str(row.entry_number), row.status.value, row.unit_code],
        route_hint=f"/projects/{row.project_id}/commercial/measurements",
        source_updated_at=row.updated_at,
    )


async def ra_bill_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        row_id = UUID(entity_id)
    except ValueError:
        return None
    row = await db.scalar(
        select(RABill).where(RABill.id == row_id, RABill.organization_id == organization_id)
    )
    if row is None:
        return None
    return SearchProjection(
        entity_type="ra_bill",
        entity_id=str(row.id),
        entity_version=row.revision,
        required_permission_key="commercial.ra_bill.view",
        scope_type="project",
        scope_id=str(row.project_id),
        title=f"RA Bill {row.bill_number}",
        subtitle=f"{row.status.value} · {row.currency_code} {row.net_payable}",
        body=row.notes or "",
        keywords=[row.bill_number, row.status.value, row.currency_code],
        route_hint=f"/projects/{row.project_id}/commercial/ra-bills/{row.id}",
        source_updated_at=row.updated_at,
    )


for entity_type, provider in (
    ("commercial_party", party_search_projection),
    ("wbs_code", wbs_search_projection),
    ("boq", boq_search_projection),
    ("measurement_entry", measurement_search_projection),
    ("ra_bill", ra_bill_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
